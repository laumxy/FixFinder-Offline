import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.database.db import seed_database
from fixfinder_engine.config import settings


def main() -> None:
    count = seed_database(settings.database_path, settings.seed_data_path, reset=True)
    print(f"Initialized {settings.database_path} with {count} problems.")


if __name__ == "__main__":
    main()
