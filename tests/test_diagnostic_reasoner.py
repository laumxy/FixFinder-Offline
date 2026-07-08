from backend.knowledge_factory.diagnostic_reasoner import DiagnosticReasoner
from backend.knowledge_factory.diagnostic_lookup import DiagnosticLookup
import os


def test_diagnostic_reasoner_and_lookup(tmp_path):
    dr = DiagnosticReasoner(output_dir=tmp_path)
    objs = [{"id": "r1", "metadata": {"problem": "Motorcycle won't start"}}]
    res = dr.generate_for_objects(objs)

    assert os.path.exists(res["path"])
    assert isinstance(res["summary"], dict)
    assert res["summary"]["total_trees"] >= 5

    dl = DiagnosticLookup(db_path=res["path"])
    qs = dl.get_questions_for_repair("r1")

    assert isinstance(qs, list)
    assert len(qs) >= 5
    assert any("engine crank" in q["question"].lower() or "battery/power" in q["question"].lower() for q in qs)


def test_diagnostic_ranking_contains_cause_scores(tmp_path):
    dr = DiagnosticReasoner(output_dir=tmp_path)
    objs = [{"id": "r2", "metadata": {"problem": "Engine overheats when idling"}}]
    res = dr.generate_for_objects(objs)

    assert os.path.exists(res["path"])
    assert res["summary"]["total_trees"] >= 5
    # verify the diagnostics graph contains overheated-related causes
    graph_data = dr.graph_path.read_text(encoding="utf-8")
    assert "coolant_leak" in graph_data or "radiator_blockage" in graph_data
