"""
Knowledge Pack Manager — build, export, and install portable knowledge packages.

A knowledge pack is a gzip-compressed JSON file containing validated
KnowledgeProblem records. Packs can be distributed offline (USB, LAN share)
and installed without internet access.

Pack file format (after gzip decompression):
{
  "schema_version": "1.0",
  "pack_id": "...",
  "name": "...",
  "description": "...",
  "industries": ["roofing", "plumbing"],
  "version": "1.0",
  "created_at": "...",
  "record_count": N,
  "records": [ { ...KnowledgeProblem fields... }, ... ]
}
"""
from __future__ import annotations

import gzip
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.database.db import (
    fetch_all_problem_records,
    get_connection,
    insert_problem,
    latest_version,
    next_patch_version,
    record_version,
    upsert_problem,
)
from app.database.models import KnowledgeProblem
from app.retrieval.faiss_index import FaissSearch
from app.utils.logger import get_logger
from fixfinder_engine.config import settings
from app.knowledge.pack_generator import PackGenerator
from app.knowledge.validator import ValidationEngine


logger = get_logger(__name__)
MAX_PACK_BYTES = settings.max_pack_size_mb * 1024 * 1024


class KnowledgePackManager:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.database_path
        self.packs_dir = settings.packs_dir
        self.packs_dir.mkdir(parents=True, exist_ok=True)

    # ── Build ─────────────────────────────────────────────────────────────────

    def build_pack(
        self,
        name: str,
        description: str = "",
        industries: list[str] | None = None,
        version: str = "1.0",
    ) -> dict[str, Any]:
        """Export a subset of the knowledge base as a .fixpack.gz file."""
        records = fetch_all_problem_records(self.db_path)
        if industries:
            records = [r for r in records if r["category"] in industries]

        if not records:
            return {"success": False, "message": "No records matched the specified industries."}

        pack_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()

        pack_data = {
            "schema_version": settings.pack_schema_version,
            "pack_id": pack_id,
            "name": name,
            "description": description,
            "industries": industries or list({r["category"] for r in records}),
            "version": version,
            "created_at": now,
            "record_count": len(records),
            "records": records,
        }

        raw = json.dumps(pack_data, ensure_ascii=False, indent=2).encode("utf-8")
        if len(raw) > MAX_PACK_BYTES:
            return {
                "success": False,
                "message": f"Pack exceeds {settings.max_pack_size_mb} MB limit. Filter by fewer industries.",
            }

        filename = f"{pack_id}_{name.lower().replace(' ', '_')}.fixpack.gz"
        file_path = self.packs_dir / filename
        with gzip.open(file_path, "wb") as f:
            f.write(raw)

        file_size = file_path.stat().st_size
        self._register_pack(
            pack_id=pack_id,
            name=name,
            description=description,
            industries=pack_data["industries"],
            version=version,
            file_path=str(file_path),
            file_size_bytes=file_size,
            record_count=len(records),
            installed=False,
        )

        logger.info("Built knowledge pack %s with %d records → %s", pack_id, len(records), file_path)
        return {
            "success": True,
            "pack_id": pack_id,
            "name": name,
            "record_count": len(records),
            "file_path": str(file_path),
            "file_size_bytes": file_size,
        }

    def generate_pack(self, name: str, description: str = "", industries: list[str] | None = None, version: str = "1.0", incremental_since: str | None = None) -> dict[str, Any]:
        """High-level generator that creates a compressed pack with extra artifacts and updates PWA manifest."""
        gen = PackGenerator(self.packs_dir)
        meta = gen.generate_pack(name=name, description=description, industries=industries, version=version, incremental_since=incremental_since)
        # register pack in DB
        self._register_pack(
            pack_id=meta["pack_id"],
            name=name,
            description=description,
            industries=industries or [],
            version=version,
            file_path=meta["file"],
            file_size_bytes=meta["size_bytes"],
            record_count=meta["record_count"],
            installed=False,
        )
        return meta

    # ── Install ───────────────────────────────────────────────────────────────

    def install_pack(self, file_path: str) -> dict[str, Any]:
        """Install a .fixpack.gz file into the knowledge base."""
        path = Path(file_path)
        if not path.exists():
            # Try relative to packs_dir
            path = self.packs_dir / file_path
        if not path.exists():
            return {"success": False, "message": f"Pack file not found: {file_path}"}

        try:
            with gzip.open(path, "rb") as f:
                pack_data = json.loads(f.read().decode("utf-8"))
        except Exception as exc:
            return {"success": False, "message": f"Failed to read pack: {exc}"}

        schema_ver = pack_data.get("schema_version", "1.0")
        if schema_ver != settings.pack_schema_version:
            return {
                "success": False,
                "message": f"Unsupported pack schema version: {schema_ver}",
            }

        records_raw = pack_data.get("records", [])
        if not records_raw:
            return {"success": False, "message": "Pack contains no records."}

        current_ver = latest_version(self.db_path)
        new_ver = next_patch_version(current_ver)

        accepted = 0
        skipped = 0
        errors = 0

        with get_connection(self.db_path) as conn:
            for raw in records_raw:
                try:
                    raw["knowledge_version"] = new_ver
                    raw["source_type"] = raw.get("source_type", "pack")
                    problem = KnowledgeProblem.model_validate(raw)
                    validator = ValidationEngine(self.db_path)
                    v = validator.validate(problem, connection=conn)
                    if not v.get("valid"):
                        skipped += 1
                        continue
                    upsert_problem(conn, problem)
                    accepted += 1
                except Exception:
                    errors += 1

            if accepted:
                total = int(conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0])
                record_version(conn, new_ver, total, f"Installed pack {pack_data.get('pack_id', '?')}")

        if accepted:
            self._rebuild_faiss()
            self._mark_pack_installed(pack_data.get("pack_id", ""), str(path))

        # If any skipped or errors, create validation report
        if skipped or errors:
            try:
                validator = ValidationEngine(self.db_path)
                reports = []
                # we only have counts here; create a minimal report
                if skipped:
                    reports.append({"note": f"skipped_records", "count": skipped})
                if errors:
                    reports.append({"note": f"errors", "count": errors})
                report_path = validator.generate_report(reports, tag=f"install_{pack_data.get('pack_id','?')}")
                self._mark_pack_installed(pack_data.get("pack_id", ""), str(path))
            except Exception:
                report_path = ""
        else:
            report_path = ""

        logger.info(
            "Installed pack %s: accepted=%d skipped=%d errors=%d",
            pack_data.get("pack_id"), accepted, skipped, errors,
        )
        return {
            "success": True,
            "pack_id": pack_data.get("pack_id"),
            "pack_name": pack_data.get("name"),
            "accepted": accepted,
            "skipped": skipped,
            "errors": errors,
            "new_version": new_ver if accepted else current_ver,
            "validation_report_path": report_path,
        }

    # ── List ──────────────────────────────────────────────────────────────────

    def list_packs(self, installed_only: bool = False) -> list[dict[str, Any]]:
        if not self.db_path.exists():
            return []
        query = "SELECT * FROM knowledge_packs"
        params: list = []
        if installed_only:
            query += " WHERE installed=1"
        query += " ORDER BY created_at DESC"
        with get_connection(self.db_path) as conn:
            rows = conn.execute(query, params).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["industries"] = json.loads(d.get("industries") or "[]")
            result.append(d)
        return result

    # ── Private ───────────────────────────────────────────────────────────────

    def _register_pack(
        self,
        pack_id: str,
        name: str,
        description: str,
        industries: list[str],
        version: str,
        file_path: str,
        file_size_bytes: int,
        record_count: int,
        installed: bool,
    ) -> None:
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO knowledge_packs
                    (pack_id, name, description, industries, version,
                     file_path, file_size_bytes, record_count, installed)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    pack_id, name, description,
                    json.dumps(industries), version,
                    file_path, file_size_bytes, record_count,
                    1 if installed else 0,
                ),
            )

    def _mark_pack_installed(self, pack_id: str, file_path: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                UPDATE knowledge_packs
                SET installed=1, installed_at=?, file_path=?
                WHERE pack_id=?
                """,
                (now, file_path, pack_id),
            )

    def _rebuild_faiss(self) -> None:
        try:
            records = fetch_all_problem_records(self.db_path)
            search = FaissSearch(
                settings.faiss_index_path,
                settings.faiss_metadata_path,
                settings.embedding_model_name,
            )
            search.rebuild(records)
        except Exception as exc:
            logger.warning("FAISS rebuild after pack install failed: %s", exc)
