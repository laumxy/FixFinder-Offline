import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.database.models import LearningRequest
from app.knowledge.updater import KnowledgeUpdater


def main() -> None:
    source_file = PROJECT_ROOT / "data" / "learning_sources.json"
    payload = json.loads(source_file.read_text(encoding="utf-8"))
    request = LearningRequest.model_validate(payload)
    result = KnowledgeUpdater().learn(request)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
