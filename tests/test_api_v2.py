"""
tests/test_api_v2.py
=====================
End-to-end tests for the FixFinder /v2 REST API using FastAPI's
TestClient (no running server required).

Run:
    python tests/test_api_v2.py              # custom runner + summary
    pytest tests/test_api_v2.py -v           # pytest
"""

from __future__ import annotations

import os
import sys
import traceback
import argparse

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fastapi.testclient import TestClient
from main import app

client = TestClient(app, raise_server_exceptions=False)

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

def _g(s): return f"\033[32m{s}\033[0m"
def _r(s): return f"\033[31m{s}\033[0m"
def _y(s): return f"\033[33m{s}\033[0m"
def _b(s): return f"\033[1m{s}\033[0m"

_PASS = _g("PASS")
_FAIL = _r("FAIL")

def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)

# ---------------------------------------------------------------------------
# Per-version fixtures
# ---------------------------------------------------------------------------

FIXTURES = {
    1: {
        "label":        "Home Maintenance",
        "search_query": "roof leaking after heavy rain near chimney",
        "system_id":    "ROF-001",
        "symptom_id":   "PRB-ROF-002",
        "repair_id":    "rep_roof_shingle",
        "analyze_text": "electrical outlet completely dead no power",
        "tree_code":    "PRB-ROF-002",
        "diagnose": {
            "symptom_code": "PRB-ROF-002",
            "responses": ["yes", "no", "yes", "no", "yes"],
        },
        "recommend": {
            "symptom_code": "PRB-ROF-002",
            "diagnostic_result": {
                "repair_code": "RP-ROF-001",
                "category": "Roofing",
                "recommended_action": "Replace damaged shingles",
            },
        },
        "parts_repair_id": "RP-ROF-001",
        "plan": {
            "symptom_code": "PRB-ROF-002",
            "diagnostic_result": {
                "repair_code": "RP-ROF-001",
                "category": "Roofing",
            },
        },
    },
    2: {
        "label":        "Electronics",
        "search_query": "iPhone battery not charging drains fast",
        "system_id":    "PHN-001",
        "symptom_id":   "PRB-PHN-001",
        "repair_id":    "rep_ph_bat",
        "analyze_text": "laptop overheating fan running loud shuts down",
        "tree_code":    "PRB-PHN-001",
        "diagnose": {
            "symptom_code": "PRB-PHN-001",
            "responses": ["no", "yes", "no", "yes"],
        },
        "recommend": {
            "symptom_code": "PRB-PHN-001",
            "diagnostic_result": {
                "repair_code": "RP-PHN-001",
                "category": "Phones",
                "recommended_action": "Replace phone battery",
            },
        },
        "parts_repair_id": "RP-PHN-001",
        "plan": {
            "symptom_code": "PRB-PHN-001",
            "diagnostic_result": {
                "repair_code": "RP-PHN-001",
                "category": "Phones",
            },
        },
    },
    3: {
        "label":        "Industrial / Automotive",
        "search_query": "check engine light O2 sensor misfire highway",
        "system_id":    "CAR-001",
        "symptom_id":   "PRB-CAR-001",
        "repair_id":    "rep_car_o2",
        "analyze_text": "excavator hydraulic arm slow leaking oil",
        "tree_code":    "PRB-CAR-001",
        "diagnose": {
            "symptom_code": "PRB-CAR-001",
            "responses": ["no", "yes", "yes", "no"],
        },
        "recommend": {
            "symptom_code": "PRB-CAR-001",
            "diagnostic_result": {
                "repair_code": "RP-CAR-001",
                "category": "Cars",
                "recommended_action": "Replace O2 sensor",
            },
        },
        "parts_repair_id": "RP-CAR-001",
        "plan": {
            "symptom_code": "PRB-CAR-001",
            "diagnostic_result": {
                "repair_code": "RP-CAR-001",
                "category": "Cars",
            },
        },
    },
}

# ===========================================================================
# Root & health tests (version-independent)
# ===========================================================================

def test_v2_root():
    """GET /v2/ returns API info dict with endpoints key."""
    r = client.get("/v2/")
    _assert(r.status_code == 200, f"GET /v2/ returned {r.status_code}")
    d = r.json()
    _assert("api" in d,        "Missing 'api' key in /v2/ response")
    _assert("endpoints" in d,  "Missing 'endpoints' key in /v2/ response")
    _assert("versions" in d,   "Missing 'versions' key in /v2/ response")
    _assert(len(d["versions"]) == 3, f"Expected 3 versions, got {len(d['versions'])}")


def test_v2_health():
    """GET /v2/health returns status and per-version breakdown."""
    r = client.get("/v2/health")
    _assert(r.status_code == 200, f"GET /v2/health returned {r.status_code}")
    d = r.json()
    _assert("status"   in d, "Missing 'status' in health response")
    _assert("versions" in d, "Missing 'versions' in health response")
    for v in ("1", "2", "3"):
        _assert(v in d["versions"], f"Version {v} missing from health response")
        vs = d["versions"][v]
        for engine in ("retrieval", "diagnostic", "repair"):
            _assert(engine in vs,
                    f"Engine '{engine}' missing from v{v} health response")
            _assert("ok" in vs[engine],
                    f"'ok' key missing from v{v}/{engine} health response")


def test_invalid_version_search():
    """POST /v2/9/search must return 422 for an invalid version."""
    r = client.post("/v2/9/search", json={"query": "test"})
    _assert(r.status_code == 422, f"Expected 422 for invalid version, got {r.status_code}")


def test_empty_search_query():
    """POST /v2/1/search with a 1-char query must return 422 (Pydantic min_length)."""
    r = client.post("/v2/1/search", json={"query": "x"})
    _assert(r.status_code == 422, f"Expected 422 for too-short query, got {r.status_code}")


# ===========================================================================
# Per-version test functions
# ===========================================================================

# ── Retrieval ─────────────────────────────────────────────────────────────────

def test_search(version: int, fx: dict):
    """POST /{version}/search returns ranked results."""
    r = client.post(f"/v2/{version}/search",
                    json={"query": fx["search_query"], "top_k": 5})
    _assert(r.status_code == 200, f"search returned {r.status_code}: {r.text[:200]}")
    d = r.json()
    _assert("results"       in d, "Missing 'results' key")
    _assert("total_results" in d, "Missing 'total_results' key")
    _assert(isinstance(d["results"], list), "'results' must be a list")
    _assert(len(d["results"]) > 0, "search returned zero results")
    first = d["results"][0]
    for key in ("rank", "entity_id", "entity_type", "score"):
        _assert(key in first, f"Missing '{key}' in first result")
    _assert(first["rank"] == 1, "First result rank must be 1")
    _assert(0.0 <= first["score"] <= 1.01,
            f"Score {first['score']} out of [0,1] range")


def test_search_entity_type_filter(version: int, fx: dict):
    """POST /{version}/search with entity_type='system' returns only systems."""
    r = client.post(f"/v2/{version}/search",
                    json={"query": fx["search_query"], "top_k": 5,
                          "entity_type": "system"})
    _assert(r.status_code == 200, f"search filter returned {r.status_code}")
    for res in r.json()["results"]:
        _assert(res["entity_type"] == "system",
                f"entity_type filter broken: got {res['entity_type']!r}")


def test_get_system(version: int, fx: dict):
    """GET /{version}/systems/{id} returns required fields."""
    r = client.get(f"/v2/{version}/systems/{fx['system_id']}")
    _assert(r.status_code == 200,
            f"get_system {fx['system_id']} returned {r.status_code}: {r.text[:200]}")
    d = r.json()
    for key in ("system_id", "system_name", "brand",
                "lifespan_years", "specifications"):
        _assert(key in d, f"Missing '{key}' in system response")


def test_get_system_not_found(version: int, fx: dict):
    """GET /{version}/systems/DOES-NOT-EXIST returns 404."""
    r = client.get(f"/v2/{version}/systems/DOES-NOT-EXIST-999")
    _assert(r.status_code == 404,
            f"Expected 404 for unknown system, got {r.status_code}")


def test_get_symptom(version: int, fx: dict):
    """GET /{version}/symptoms/{id} returns required fields."""
    r = client.get(f"/v2/{version}/symptoms/{fx['symptom_id']}")
    _assert(r.status_code == 200,
            f"get_symptom {fx['symptom_id']} returned {r.status_code}: {r.text[:200]}")
    d = r.json()
    for key in ("symptom_id", "symptom_name", "severity",
                "description", "causes"):
        _assert(key in d, f"Missing '{key}' in symptom response")


def test_get_symptom_not_found(version: int, fx: dict):
    """GET /{version}/symptoms/DOES-NOT-EXIST returns 404."""
    r = client.get(f"/v2/{version}/symptoms/DOES-NOT-EXIST-999")
    _assert(r.status_code == 404,
            f"Expected 404 for unknown symptom, got {r.status_code}")


def test_get_repair(version: int, fx: dict):
    """GET /{version}/repairs/{id} returns required fields."""
    r = client.get(f"/v2/{version}/repairs/{fx['repair_id']}")
    _assert(r.status_code == 200,
            f"get_repair {fx['repair_id']} returned {r.status_code}: {r.text[:200]}")
    d = r.json()
    for key in ("repair_id", "repair_name", "overview",
                "tools_required", "procedure_steps", "difficulty"):
        _assert(key in d, f"Missing '{key}' in repair response")


def test_get_repair_not_found(version: int, fx: dict):
    """GET /{version}/repairs/DOES-NOT-EXIST returns 404."""
    r = client.get(f"/v2/{version}/repairs/DOES-NOT-EXIST-999")
    _assert(r.status_code == 404,
            f"Expected 404 for unknown repair, got {r.status_code}")


# ── Diagnostic ────────────────────────────────────────────────────────────────

def test_analyze_symptoms(version: int, fx: dict):
    """POST /{version}/analyze returns ranked symptom matches."""
    r = client.post(f"/v2/{version}/analyze",
                    json={"text": fx["analyze_text"], "top_k": 5})
    _assert(r.status_code == 200,
            f"analyze returned {r.status_code}: {r.text[:200]}")
    d = r.json()
    _assert("matches"       in d, "Missing 'matches' key")
    _assert("total_matches" in d, "Missing 'total_matches' key")
    _assert(isinstance(d["matches"], list), "'matches' must be a list")
    _assert(len(d["matches"]) > 0, "analyze returned zero matches")
    first = d["matches"][0]
    for key in ("rank", "symptom_code", "symptom_name", "severity", "score"):
        _assert(key in first, f"Missing '{key}' in first match")
    _assert(first["rank"] == 1, "First match rank must be 1")
    scores = [m["score"] for m in d["matches"]]
    _assert(scores == sorted(scores, reverse=True),
            f"Matches not sorted by descending score: {scores}")


def test_analyze_empty_text():
    """POST /v2/1/analyze with text below min_length returns 422."""
    r = client.post("/v2/1/analyze", json={"text": "ab"})
    _assert(r.status_code == 422,
            f"Expected 422 for too-short text, got {r.status_code}")


def test_get_tree(version: int, fx: dict):
    """GET /{version}/tree/{symptom_code} returns a complete tree or 404."""
    r = client.get(f"/v2/{version}/tree/{fx['tree_code']}")
    # The tree may not exist in JSON (DB codes ≠ JSON codes) — both are valid
    _assert(r.status_code in (200, 404),
            f"tree returned unexpected {r.status_code}: {r.text[:200]}")
    if r.status_code == 200:
        d = r.json()
        for key in ("id", "name", "steps", "decision_points", "resolution_paths"):
            _assert(key in d, f"Missing '{key}' in tree response")
        _assert(len(d["steps"])           > 0, "tree has no steps")
        _assert(len(d["decision_points"]) > 0, "tree has no decision_points")
        _assert(len(d["resolution_paths"]) > 0, "tree has no resolution_paths")


def test_get_tree_not_found(version: int, fx: dict):
    """GET /{version}/tree/DOES-NOT-EXIST returns 404."""
    r = client.get(f"/v2/{version}/tree/DOES-NOT-EXIST-999")
    _assert(r.status_code == 404,
            f"Expected 404 for unknown tree code, got {r.status_code}")


def test_run_diagnostic(version: int, fx: dict):
    """POST /{version}/diagnose returns required keys."""
    body = fx["diagnose"]
    r = client.post(f"/v2/{version}/diagnose", json=body)
    _assert(r.status_code == 200,
            f"diagnose returned {r.status_code}: {r.text[:200]}")
    d = r.json()
    for key in ("symptom_code", "recommended_action",
                "decisions_made", "diagnosis_complete", "remaining_steps"):
        _assert(key in d, f"Missing '{key}' in diagnose response")
    _assert(isinstance(d["decisions_made"], list),
            "'decisions_made' must be a list")
    _assert(bool(d["recommended_action"]),
            "recommended_action must not be empty")


def test_run_diagnostic_no_responses(version: int, fx: dict):
    """POST /{version}/diagnose with empty responses still returns a result."""
    r = client.post(f"/v2/{version}/diagnose",
                    json={"symptom_code": fx["diagnose"]["symptom_code"],
                          "responses": []})
    _assert(r.status_code == 200,
            f"diagnose (no responses) returned {r.status_code}: {r.text[:200]}")
    _assert("recommended_action" in r.json(),
            "Missing recommended_action with empty responses")


# ── Repair Reasoning ──────────────────────────────────────────────────────────

def test_recommend_repair(version: int, fx: dict):
    """POST /{version}/recommend returns ranked recommendations."""
    r = client.post(f"/v2/{version}/recommend", json=fx["recommend"])
    _assert(r.status_code == 200,
            f"recommend returned {r.status_code}: {r.text[:200]}")
    d = r.json()
    _assert("recommendations" in d, "Missing 'recommendations' key")
    _assert("total_results"   in d, "Missing 'total_results' key")
    recs = d["recommendations"]
    _assert(len(recs) > 0, "recommend returned zero recommendations")
    first = recs[0]
    for key in ("rank", "id", "name", "difficulty",
                "relevance_score", "procedure_steps"):
        _assert(key in first, f"Missing '{key}' in first recommendation")
    _assert(first["rank"] == 1, "First recommendation rank must be 1")
    # Direct repair_code match must always rank first
    diag = fx["recommend"].get("diagnostic_result", {})
    if diag.get("repair_code"):
        _assert(first["id"] == diag["repair_code"],
                f"Direct repair_code {diag['repair_code']!r} "
                f"should rank 1, got {first['id']!r}")


def test_recommend_scores_in_range(version: int, fx: dict):
    """All relevance scores are within [0, 1]."""
    r = client.post(f"/v2/{version}/recommend", json=fx["recommend"])
    _assert(r.status_code == 200, f"recommend returned {r.status_code}")
    for rec in r.json()["recommendations"]:
        _assert(0.0 <= rec["relevance_score"] <= 1.0,
                f"score {rec['relevance_score']} out of range")


def test_parts_availability(version: int, fx: dict):
    """GET /{version}/parts/{id} returns correct structure."""
    r = client.get(f"/v2/{version}/parts/{fx['parts_repair_id']}")
    _assert(r.status_code == 200,
            f"parts returned {r.status_code}: {r.text[:200]}")
    d = r.json()
    for key in ("repair_id", "materials_needed", "parts",
                "total_parts_cost", "all_parts_available",
                "missing_parts", "low_stock_parts"):
        _assert(key in d, f"Missing '{key}' in parts response")
    _assert(isinstance(d["parts"], list), "'parts' must be a list")
    _assert(d["total_parts_cost"] >= 0,
            f"total_parts_cost must be >= 0, got {d['total_parts_cost']}")
    valid_statuses = {"in_stock", "low_stock", "out_of_stock", "not_found"}
    for p in d["parts"]:
        _assert(p["status"] in valid_statuses,
                f"Invalid part status: {p['status']!r}")


def test_parts_materials_count_matches(version: int, fx: dict):
    """len(parts) == len(materials_needed)."""
    r = client.get(f"/v2/{version}/parts/{fx['parts_repair_id']}")
    _assert(r.status_code == 200, f"parts returned {r.status_code}")
    d = r.json()
    _assert(len(d["parts"]) == len(d["materials_needed"]),
            f"parts({len(d['parts'])}) != materials_needed({len(d['materials_needed'])})")


def test_generate_plan(version: int, fx: dict):
    """POST /{version}/plan returns complete plan structure."""
    r = client.post(f"/v2/{version}/plan", json=fx["plan"])
    _assert(r.status_code == 200,
            f"plan returned {r.status_code}: {r.text[:200]}")
    d = r.json()
    for key in ("symptom_code", "summary", "difficulty", "urgency",
                "total_estimated_time_minutes", "total_parts_cost",
                "all_parts_available", "plan_steps",
                "primary_repair", "alternative_repairs"):
        _assert(key in d, f"Missing '{key}' in plan response")
    _assert(bool(d["summary"]),     "summary must not be empty")
    _assert(d["total_parts_cost"] >= 0, "total_parts_cost must be >= 0")
    _assert(d["total_estimated_time_minutes"] >= 0,
            "total_estimated_time_minutes must be >= 0")
    _assert(d["urgency"] in
            {"Immediate", "Urgent", "Normal", "Routine", "Unknown"},
            f"Invalid urgency: {d['urgency']!r}")
    _assert(isinstance(d["plan_steps"], list), "'plan_steps' must be a list")
    if d["primary_repair"]:
        _assert("parts_availability" in d["primary_repair"],
                "primary_repair missing 'parts_availability'")
    _assert(d["symptom_code"] == fx["plan"]["symptom_code"],
            "symptom_code mismatch in plan response")


def test_plan_steps_nonempty(version: int, fx: dict):
    """plan_steps must have at least one entry when primary repair found."""
    r = client.post(f"/v2/{version}/plan", json=fx["plan"])
    _assert(r.status_code == 200, f"plan returned {r.status_code}")
    d = r.json()
    if d["primary_repair"] is not None:
        _assert(len(d["plan_steps"]) > 0,
                "plan_steps empty despite primary_repair being set")

# ===========================================================================
# Test runner
# ===========================================================================

_STANDALONE_TESTS = [
    # (name, fn)
    ("v2_root",             test_v2_root),
    ("v2_health",           test_v2_health),
    ("invalid_version",     test_invalid_version_search),
    ("empty_search_query",  test_empty_search_query),
    ("analyze_empty_text",  test_analyze_empty_text),
]

_PER_VERSION_TESTS = [
    # (name, fn)
    ("search",                    test_search),
    ("search_entity_type_filter", test_search_entity_type_filter),
    ("get_system",                test_get_system),
    ("get_system_not_found",      test_get_system_not_found),
    ("get_symptom",               test_get_symptom),
    ("get_symptom_not_found",     test_get_symptom_not_found),
    ("get_repair",                test_get_repair),
    ("get_repair_not_found",      test_get_repair_not_found),
    ("analyze_symptoms",          test_analyze_symptoms),
    ("get_tree",                  test_get_tree),
    ("get_tree_not_found",        test_get_tree_not_found),
    ("run_diagnostic",            test_run_diagnostic),
    ("run_diagnostic_no_responses", test_run_diagnostic_no_responses),
    ("recommend_repair",          test_recommend_repair),
    ("recommend_scores_in_range", test_recommend_scores_in_range),
    ("parts_availability",        test_parts_availability),
    ("parts_materials_count",     test_parts_materials_count_matches),
    ("generate_plan",             test_generate_plan),
    ("plan_steps_nonempty",       test_plan_steps_nonempty),
]

# inject pytest-compatible wrappers into module namespace
def _make_pytest_standalone(name, fn):
    def _t(): fn()
    _t.__name__ = f"test_{name}"
    return _t

def _make_pytest_versioned(name, fn, version, fx):
    def _t(): fn(version, fx)
    _t.__name__ = f"test_{name}_v{version}"
    return _t

for _name, _fn in _STANDALONE_TESTS:
    globals()[f"test_{_name}"] = _make_pytest_standalone(_name, _fn)

for _v, _fx in FIXTURES.items():
    for _name, _fn in _PER_VERSION_TESTS:
        globals()[f"test_{_name}_v{_v}"] = _make_pytest_versioned(_name, _fn, _v, _fx)


def run_all_tests() -> None:
    total = passed = failed = 0

    print()
    print(_b("=" * 64))
    print(_b("  FixFinder /v2 API Tests"))
    print(_b("=" * 64))

    # --- standalone ---
    print(_b("\n  [ Version-independent ]"))
    for name, fn in _STANDALONE_TESTS:
        total += 1
        label = f"  {name:<45s}"
        try:
            fn()
            print(f"{label} {_PASS}")
            passed += 1
        except AssertionError as exc:
            print(f"{label} {_FAIL}  — {exc}")
            failed += 1
        except Exception as exc:
            print(f"{label} {_FAIL}  — {type(exc).__name__}: {exc}")
            if os.environ.get("FF_DEBUG"):
                traceback.print_exc()
            failed += 1

    # --- per version ---
    for version, fx in FIXTURES.items():
        print(_b(f"\n  [ Version {version} — {fx['label']} ]"))
        for name, fn in _PER_VERSION_TESTS:
            total += 1
            label = f"  {name:<45s}"
            try:
                fn(version, fx)
                print(f"{label} {_PASS}")
                passed += 1
            except AssertionError as exc:
                print(f"{label} {_FAIL}  — {exc}")
                failed += 1
            except Exception as exc:
                print(f"{label} {_FAIL}  — {type(exc).__name__}: {exc}")
                if os.environ.get("FF_DEBUG"):
                    traceback.print_exc()
                failed += 1

    print()
    print(_b("=" * 64))
    print(_b(f"  Results: {passed}/{total} passed"))
    if failed:
        print(_r(f"  {failed} FAILED"))
    print(_b("=" * 64))
    print()

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FixFinder v2 API Tests")
    parser.add_argument("--tests-only", action="store_true")
    args = parser.parse_args()
    run_all_tests()
