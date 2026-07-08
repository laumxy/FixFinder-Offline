from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.knowledge.cleaner import KnowledgeCleaner


class DocumentParser:
    """Convert raw document sources into normalized text and structured metadata."""

    def __init__(self) -> None:
        self.cleaner = KnowledgeCleaner()

    def parse_text_file(self, path: str | Path) -> str:
        with Path(path).open("r", encoding="utf-8", errors="ignore") as handle:
            raw = handle.read()
        return self.cleaner.clean_text(raw)

    def parse_json_file(self, path: str | Path) -> str:
        with Path(path).open("r", encoding="utf-8", errors="ignore") as handle:
            payload = json.load(handle)

        if isinstance(payload, dict):
            return self._flatten_json(payload)
        if isinstance(payload, list):
            return self._flatten_json({"items": payload})
        return self.cleaner.clean_text(str(payload))

    def parse_csv_file(self, path: str | Path, text_columns: list[str] | None = None) -> str:
        import csv

        with Path(path).open("r", encoding="utf-8", errors="ignore") as handle:
            reader = csv.DictReader(handle)
            rows = [row for row in reader]

        if not rows:
            return ""

        text_columns = text_columns or [key for key in rows[0].keys() if key.lower() in {"description", "details", "notes", "text", "symptoms", "causes", "procedure"}]
        text_rows: list[str] = []
        for row in rows:
            for key in text_columns:
                value = row.get(key)
                if value:
                    text_rows.append(str(value))

        return self.cleaner.clean_text("\n".join(text_rows))

    def parse_html_file(self, path: str | Path) -> str:
        from bs4 import BeautifulSoup

        with Path(path).open("r", encoding="utf-8", errors="ignore") as handle:
            raw = handle.read()

        parsed = BeautifulSoup(raw, "html.parser")
        for tag in parsed.find_all("script") + parsed.find_all("style"):
            tag.decompose()

        return self.cleaner.clean_text(parsed.get_text(separator="\n"))

    def parse_docx_file(self, path: str | Path) -> str:
        from docx import Document

        doc = Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return self.cleaner.clean_text("\n".join(paragraphs))

    def _flatten_json(self, payload: Any) -> str:
        if isinstance(payload, dict):
            parts: list[str] = []
            for key, value in payload.items():
                parts.append(str(key))
                parts.append(self._flatten_json(value))
            return "\n".join([part for part in parts if part])
        if isinstance(payload, list):
            return "\n".join(self._flatten_json(item) for item in payload if item)
        return str(payload)
