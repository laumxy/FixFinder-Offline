"""
Load extra seed records from data/seed_extra.json into the database.
This is additive — it does NOT reset the existing data.
"""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.database.db import (
    ensure_database,
    get_connection,
    latest_version,
    next_patch_version,
    record_version,
    upsert_problem,
)
from app.database.models import KnowledgeProblem
from fixfinder_engine.config import settings


def main() -> None:
    extra_path = PROJECT_ROOT / "data" / "seed_extra.json"
    if not extra_path.exists():
        print("seed_extra.json not found.")
        return

    ensure_database(settings.database_path)
    raw = json.loads(extra_path.read_text(encoding="utf-8"))
    problems = [KnowledgeProblem.model_validate(item) for item in raw]

    current_ver = latest_version(settings.database_path)
    new_ver = next_patch_version(current_ver)

    inserted = 0
    updated = 0
    with get_connection(settings.database_path) as conn:
        for problem in problems:
            existing = conn.execute(
                "SELECT id FROM problems WHERE category=? AND problem=?",
                (problem.category, problem.problem),
            ).fetchone()
            upsert_problem(conn, problem)
            if existing:
                updated += 1
            else:
                inserted += 1

        total = int(conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0])
        if inserted > 0:
            record_version(conn, new_ver, total, f"Loaded {inserted} extra seed records.")

    print(f"Extra seed: inserted={inserted}, updated={updated}, total={total}")
    print(f"Knowledge version: {new_ver if inserted else current_ver}")


if __name__ == "__main__":
    main()
