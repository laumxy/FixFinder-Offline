import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.database.db import ensure_database, fetch_all_problem_records
from app.retrieval.faiss_index import FaissSearch
from fixfinder_engine.config import settings


def main() -> None:
    ensure_database(settings.database_path)
    records = fetch_all_problem_records(settings.database_path)
    if not records:
        raise SystemExit("No problems found in database.")

    search = FaissSearch(
        index_path=settings.faiss_index_path,
        metadata_path=settings.faiss_metadata_path,
        model_name=settings.embedding_model_name,
    )
    result = search.rebuild(records)
    print(f"Built FAISS index at {result['index_path']} with {result['vector_count']} vectors.")


if __name__ == "__main__":
    main()
