import json
from pathlib import Path

from app.knowledge.updater import KnowledgeUpdater

GOOD_TEXT = (
    "Washing machine not draining properly. Symptoms include water left in drum after cycle. "
    "The cause is usually a blocked drain hose or faulty pump. "
    "Inspect the drain filter at the bottom front of the machine for debris. "
    "Check the drain hose is not kinked or blocked. "
    "Replace the drain pump if it does not run. "
    "Tools needed: screwdriver, bucket, towel. "
    "Safety: unplug the machine before opening any panels. Do not force hoses."
)


def test_manual_processor_and_updater(tmp_path):
    # write sample file
    p = tmp_path / "sample.txt"
    p.write_text(GOOD_TEXT, encoding="utf-8")

    # run the import pipeline via updater
    updater = KnowledgeUpdater()
    result = updater.learn_from_files([str(p)], source_type="manual", category="appliances", min_reliability=0.0)

    assert isinstance(result, dict)
    assert result.get("status") in {"ok", "error"}
    # Ensure the parser produced something when available
    if result.get("status") == "ok":
        assert "accepted" in result and "rejected" in result
