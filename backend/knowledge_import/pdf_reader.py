from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Iterable


class PDFReader:
    """Extract plain text from PDF files without storing raw documents."""

    def __init__(self, pdf_path: str | Path) -> None:
        self.path = Path(pdf_path)

    def extract_text(self) -> str:
        """Return text for later structured processing."
        from PyPDF2 import PdfReader

        if not self.path.exists():
            raise FileNotFoundError(f"PDF file not found: {self.path}")

        reader = PdfReader(str(self.path))
        text_parts: list[str] = []
        for page in reader.pages:
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""
            if page_text:
                text_parts.append(page_text)

        return "\n".join(text_parts).strip()
