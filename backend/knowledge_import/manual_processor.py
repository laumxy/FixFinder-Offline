from __future__ import annotations

from pathlib import Path
from typing import Any

from app.database.models import LearningSource
from app.knowledge.cleaner import KnowledgeCleaner
from .document_parser import DocumentParser
from .information_extractor import InformationExtractor


class ManualProcessor:
    """High-level file processor for document import into structured knowledge."""

    def __init__(self) -> None:
        self.parser = DocumentParser()
        self.extractor = InformationExtractor()
        self.cleaner = KnowledgeCleaner()

    def process_file(
        self,
        file_path: str | Path,
        source_type: str = "manual",
        category: str = "general",
        version: str = "v1.0",
    ) -> LearningSource | None:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        suffix = path.suffix.lower()
        if suffix == ".pdf":
            from backend.knowledge_import.pdf_reader import PDFReader
            text = PDFReader(path).extract_text()
        elif suffix in {".txt"}:
            text = self.parser.parse_text_file(path)
        elif suffix in {".json"}:
            text = self.parser.parse_json_file(path)
        elif suffix in {".csv"}:
            text = self.parser.parse_csv_file(path)
        elif suffix in {".html", ".htm"}:
            text = self.parser.parse_html_file(path)
        elif suffix in {".docx"}:
            text = self.parser.parse_docx_file(path)
        else:
            return None

        text = self.cleaner.clean_text(text)
        if not text:
            return None

        knowledge = self.extractor.extract_from_source(
            text=text,
            source_type=source_type,
            category=category,
            url=str(path),
            version=version,
        )

        if knowledge is None:
            return None

        return LearningSource(
            text=text,
            url=str(path),
            category=category,
            source_type=source_type,
        )

    def process_file_batch(
        self,
        file_paths: list[str] | list[Path],
        source_type: str = "manual",
        category: str = "general",
        version: str = "v1.0",
    ) -> list[LearningSource]:
        results: list[LearningSource] = []
        for file_path in file_paths:
            source = self.process_file(file_path, source_type=source_type, category=category, version=version)
            if source:
                results.append(source)
        return results
