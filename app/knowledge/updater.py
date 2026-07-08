from typing import Any

import requests

from app.database.db import (
    fetch_all_problem_records,
    get_connection,
    latest_version,
    next_patch_version,
    record_version,
    upsert_problem,
)
from app.database.models import KnowledgeProblem, LearningRequest, LearningSource
from app.knowledge.cleaner import KnowledgeCleaner
from app.knowledge.extractor import KnowledgeExtractor
from app.retrieval.faiss_index import FaissSearch
from app.utils.logger import get_logger
from fixfinder_engine.config import settings

# Optional: file-based import pipeline
try:
    from backend.knowledge_import.manual_processor import ManualProcessor
except Exception:
    ManualProcessor = None

# Validation engine
from app.knowledge.validator import ValidationEngine


class KnowledgeUpdater:
    def __init__(self) -> None:
        self.extractor = KnowledgeExtractor()
        self.cleaner = KnowledgeCleaner()
        self.logger = get_logger(__name__)

    def learn(self, request: LearningRequest) -> dict[str, Any]:
        current_version = latest_version(settings.database_path)
        new_version = next_patch_version(current_version)
        existing = fetch_all_problem_records(settings.database_path)
        existing_keys = {(item["category"], item["problem"].lower()) for item in existing}

        accepted: list[KnowledgeProblem] = []
        rejected = 0
        validation_reports: list[dict[str, Any]] = []
        validator = ValidationEngine(settings.database_path)

        for source in request.sources:
            hydrated = self._hydrate_source(source)
            extracted = self.extractor.extract(hydrated, new_version)
            if not extracted:
                rejected += 1
                continue
            if extracted.reliability_score < request.min_reliability:
                rejected += 1
                continue
            key = (extracted.category, extracted.problem.lower())
            # validate record before accepting
            vreport = validator.validate(extracted)
            if not vreport.get("valid"):
                rejected += 1
                validation_reports.append({"problem": extracted.problem, "issues": vreport.get("issues", [])})
                continue
            if key in existing_keys:
                rejected += 1
                validation_reports.append({"problem": extracted.problem, "issues": ["duplicate_record"]})
                continue
            accepted.append(extracted)
            existing_keys.add(key)

        if accepted:
            with get_connection(settings.database_path) as connection:
                for problem in accepted:
                    upsert_problem(connection, problem)
                total_records = int(connection.execute("SELECT COUNT(*) AS total FROM problems").fetchone()["total"])
                record_version(connection, new_version, total_records, f"Learned {len(accepted)} structured records.")
            self._rebuild_faiss()

        result = {
            "status": "ok",
            "previous_version": current_version,
            "knowledge_version": new_version if accepted else current_version,
            "accepted": len(accepted),
            "rejected": rejected,
            "message": "Knowledge base updated." if accepted else "No high-quality new knowledge accepted.",
        }
        if validation_reports:
            # write validation report file
            try:
                report_path = validator.generate_report(validation_reports, tag="learn")
                result["validation_reports"] = validation_reports
                result["validation_report_path"] = report_path
            except Exception:
                result["validation_reports"] = validation_reports
        return result

    def _hydrate_source(self, source: LearningSource) -> LearningSource:
        if source.text or not source.url:
            return source
        try:
            response = requests.get(source.url, timeout=12, headers={"User-Agent": "FixFinderOfflineAI/3.0"})
            response.raise_for_status()
            text = self.cleaner.clean_text(response.text)
            return LearningSource(
                url=source.url,
                text=text,
                category=source.category,
                source_type=source.source_type,
            )
        except requests.RequestException as exc:
            self.logger.warning("Failed to fetch learning source %s: %s", source.url, exc)
            return source

    def _rebuild_faiss(self) -> None:
        records = fetch_all_problem_records(settings.database_path)
        search = FaissSearch(settings.faiss_index_path, settings.faiss_metadata_path, settings.embedding_model_name)
        search.rebuild(records)

    def learn_from_files(
        self,
        file_paths: list[str],
        source_type: str = "manual",
        category: str = "general",
        min_reliability: float = 0.55,
    ) -> dict[str, Any]:
        """Process local files via the backend.knowledge_import pipeline and learn.

        Returns same structure as `learn()`.
        """
        if ManualProcessor is None:
            self.logger.error("ManualProcessor unavailable; import pipeline not installed.")
            return {"status": "error", "message": "Import pipeline not available."}

        processor = ManualProcessor()
        sources = processor.process_file_batch(file_paths, source_type=source_type, category=category, version=latest_version(settings.database_path))
        if not sources:
            return {"status": "ok", "accepted": 0, "rejected": len(file_paths), "message": "No valid learning sources extracted from files."}

        # Wrap into LearningRequest and call existing learn path
        req = LearningRequest(sources=sources, min_reliability=min_reliability)
        return self.learn(req)
