from typing import Any

from app.database.db import ensure_database, fetch_all_problem_records
from app.retrieval.faiss_index import FaissSearch
from fixfinder_engine.config import settings


def ensure_runtime_assets(faiss_search: FaissSearch | None = None) -> dict[str, Any]:
    """
    Ensure the database and FAISS index are ready.

    Pass the pipeline's own FaissSearch instance so we don't load the
    embedding model a second time.  When called without an argument (e.g.
    from a management script) a temporary instance is created as before.
    """
    database_status = ensure_database(settings.database_path)
    records = fetch_all_problem_records(settings.database_path)

    # Reuse the caller's instance when provided — avoids a second
    # SentenceTransformer load which can cost several seconds.
    owns_instance = faiss_search is None
    if owns_instance:
        faiss_search = FaissSearch(
            index_path=settings.faiss_index_path,
            metadata_path=settings.faiss_metadata_path,
            model_name=settings.embedding_model_name,
        )

    faiss_status = faiss_search.status()

    rebuilt = False
    if records and (
        not faiss_status["index_exists"]
        or not faiss_status["metadata_exists"]
        or faiss_status["vector_count"] != len(records)
        or faiss_status["metadata_count"] != len(records)
    ):
        faiss_search.rebuild(records)
        faiss_status = faiss_search.status()
        rebuilt = True

    return {
        "database": database_status,
        "faiss": faiss_status,
        "faiss_rebuilt": rebuilt,
    }
