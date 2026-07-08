from __future__ import annotations

from app.database.models import KnowledgeProblem, LearningSource
from app.knowledge.cleaner import KnowledgeCleaner
from app.knowledge.extractor import KnowledgeExtractor


class InformationExtractor:
    """Create structured KnowledgeProblem records from normalized document text."""

    def __init__(self) -> None:
        self.extractor = KnowledgeExtractor()
        self.cleaner = KnowledgeCleaner()

    def extract_from_source(
        self,
        text: str,
        source_type: str,
        category: str = "general",
        url: str = "",
        version: str = "v1.0",
    ) -> KnowledgeProblem | None:
        source = LearningSource(
            text=text,
            category=category,
            source_type=source_type,
            url=url,
        )
        return self.extractor.extract(source, version)

    def extract_from_metadata(self, metadata: dict[str, str], version: str) -> KnowledgeProblem | None:
        text_parts: list[str] = []
        for field in ("title", "summary", "abstract", "conclusion", "content"):
            if field in metadata and metadata[field]:
                text_parts.append(metadata[field])
        if not text_parts:
            return None
        return self.extract_from_source("\n".join(text_parts), metadata.get("source_type", "manual"), metadata.get("category", "general"), metadata.get("url", ""), version)
