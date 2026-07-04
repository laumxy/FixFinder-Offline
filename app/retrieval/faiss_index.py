import json
from pathlib import Path
from typing import Any

import numpy as np

from fixfinder_engine.config import settings


def knowledge_record_to_text(record: dict[str, Any]) -> str:
    fields = [
        record.get("category", ""),
        record.get("problem", ""),
        " ".join(record.get("aliases", [])),
        " ".join(record.get("symptoms", [])),
        " ".join(record.get("causes", [])),
        " ".join(record.get("inspection_steps", [])),
        " ".join(record.get("repair_steps", [])),
        " ".join(record.get("tools", [])),
        " ".join(record.get("safety", [])),
        " ".join(record.get("prevention", [])),
    ]
    return " ".join(part for part in fields if part).lower()


class FaissSearch:
    def __init__(self, index_path: Path, metadata_path: Path, model_name: str) -> None:
        self.index_path = Path(index_path)
        self.metadata_path = Path(metadata_path)
        self.model_name = model_name
        self._index = None
        self._metadata: list[dict[str, Any]] = []
        self._model = None

    # ── Public ────────────────────────────────────────────────────────────────

    def warm_up(self) -> None:
        """
        Eagerly load the FAISS index and the embedding model so the first
        real search call doesn't pay the cold-start penalty.
        Call this once at application startup (e.g. from bootstrap).
        """
        if not self.index_path.exists() or not self.metadata_path.exists():
            return
        try:
            self._load()
        except (ImportError, RuntimeError, OSError, ValueError):
            pass

    def status(self) -> dict[str, Any]:
        index_exists = self.index_path.exists()
        metadata_exists = self.metadata_path.exists()
        vector_count = 0
        metadata_count = 0
        loaded = self._index is not None

        if metadata_exists:
            try:
                metadata_count = len(json.loads(self.metadata_path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                metadata_count = 0

        if index_exists:
            try:
                if self._index is not None:
                    vector_count = int(self._index.ntotal)
                else:
                    import faiss

                    index = faiss.read_index(str(self.index_path))
                    vector_count = int(index.ntotal)
            except (ImportError, RuntimeError, OSError, ValueError):
                loaded = False

        return {
            "available": index_exists and metadata_exists and vector_count > 0 and vector_count == metadata_count,
            "loaded": loaded,
            "index_exists": index_exists,
            "metadata_exists": metadata_exists,
            "index_path": str(self.index_path),
            "metadata_path": str(self.metadata_path),
            "model_name": self.model_name,
            "vector_count": vector_count,
            "metadata_count": metadata_count,
        }

    def search(self, query: str, category: str | None, limit: int = 5) -> list[dict[str, Any]]:
        if not self.index_path.exists() or not self.metadata_path.exists():
            return []

        try:
            self._load()
        except (ImportError, RuntimeError, OSError, ValueError):
            return []

        if self._index is None or self._model is None:
            return []

        query_embedding = self._encode([query])

        # Fetch enough candidates to satisfy both the category-filtered and
        # the category-unfiltered paths in a single FAISS call.
        fetch_k = max(limit * 5, 20)
        distances, indices = self._index.search(query_embedding, fetch_k)

        # Try category-filtered first; fall back to no filter without a second
        # round-trip to the index.
        matches = self._matches_from_results(distances, indices, category, limit)
        if not matches and category and category != "general":
            matches = self._matches_from_results(distances, indices, None, limit)

        return matches

    def rebuild(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        if not records:
            raise ValueError("Cannot build FAISS index from an empty knowledge base.")

        import faiss

        self._load_model()
        texts = [knowledge_record_to_text(record) for record in records]
        embeddings = self._encode(texts)

        index = faiss.IndexFlatIP(embeddings.shape[1])
        index.add(embeddings)

        metadata = [
            {
                "id": int(record["id"]),
                "category": record["category"],
                "problem": record["problem"],
                "aliases": record.get("aliases", []),
            }
            for record in records
        ]

        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(self.index_path))
        self.metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        self._index = index
        self._metadata = metadata
        return {
            "index_path": str(self.index_path),
            "metadata_path": str(self.metadata_path),
            "vector_count": int(index.ntotal),
            "model_name": self.model_name,
        }

    # ── Private ───────────────────────────────────────────────────────────────

    def _matches_from_results(
        self,
        distances: np.ndarray,
        indices: np.ndarray,
        category: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        matches = []
        seen_ids: set[int] = set()
        for score, index in zip(distances[0], indices[0]):
            if index < 0 or index >= len(self._metadata):
                continue
            if float(score) < settings.min_semantic_score:
                continue
            metadata = self._metadata[index]
            if category and category != "general" and metadata.get("category") != category:
                continue
            if metadata["id"] in seen_ids:
                continue
            seen_ids.add(metadata["id"])
            matches.append(
                {
                    "id": metadata["id"],
                    "category": metadata["category"],
                    "problem": metadata["problem"],
                    "aliases": metadata.get("aliases", []),
                    "score": float(score),
                    "source": "faiss",
                }
            )
            if len(matches) >= limit:
                break
        return matches

    def _load(self) -> None:
        if self._index is not None:
            return

        import faiss

        self._index = faiss.read_index(str(self.index_path))
        self._metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        self._load_model()

        if int(self._index.ntotal) != len(self._metadata):
            raise ValueError("FAISS index vector count does not match metadata count.")

    def _load_model(self) -> None:
        if self._model is not None:
            return

        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(self.model_name)

    def _encode(self, texts: list[str]) -> np.ndarray:
        self._load_model()
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return np.asarray(embeddings, dtype="float32")
