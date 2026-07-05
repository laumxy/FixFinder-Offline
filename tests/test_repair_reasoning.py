"""
tests/test_repair_reasoning.py
===============================
Functional test suite for AIRepairReasoningEngine.

Run from workspace root:
    python tests/test_repair_reasoning.py             # tests + demo
    python tests/test_repair_reasoning.py --demo      # demo only
    python tests/test_repair_reasoning.py --tests-only
    pytest tests/test_repair_reasoning.py -v
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from ai_engine.repair_reasoning_engine import AIRepairReasoningEngine

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

def _green(s: str)  -> str: return f"\033[32m{s}\033[0m"
def _red(s: str)    -> str: return f"\033[31m{s}\033[0m"
def _yellow(s: str) -> str: return f"\033[33m{s}\033[0m"
def _cyan(s: str)   -> str: return f"\033[36m{s}\033[0m"
def _bold(s: str)   -> str: return f"\033[1m{s}\033[0m"

_PASS = _green("PASS")
_FAIL = _red("FAIL")

def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)

# ===========================================================================
# Per-version test fixtures
# ===========================================================================

# Simulated diagnostic_result dicts (mirrors AIDiagnosticEngine.run_diagnostic output)
_DIAG_ROF = {
    "tree_id": "DT-ROF-001", "tree_name": "Roof Leak Diagnostic Tree",
    "symptom_code": "PRB-ROF-002", "category": "Roofing",
    "repair_code": "RP-ROF-001", "recommended_action": "Replace damaged shingles",
    "resolution_path": {"path_id": "RES-1", "repair_code": "RP-ROF-001",
                        "action": "Replace damaged shingles", "difficulty": "Moderate"},
    "diagnosis_complete": True, "severity": "High",
}
_DIAG_PLB = {
    "tree_id": "DT-PLB-001", "tree_name": "Low Water Pressure",
    "symptom_code": "PRB-PLM-002", "category": "Plumbing",
    "repair_code": "RP-PLB-001", "recommended_action": "Replace toilet flapper",
    "resolution_path": {"path_id": "RES-1", "repair_code": "RP-PLB-001",
                        "action": "Replace toilet flapper", "difficulty": "Easy"},
    "diagnosis_complete": True, "severity": "Low",
}
_DIAG_ELC = {
    "tree_id": "DT-ELC-001", "tree_name": "Outlet Not Working",
    "symptom_code": "PRB-ELC-002", "category": "Electrical",
    "repair_code": "RP-ELC-001", "recommended_action": "Replace circuit breaker",
    "resolution_path": {"path_id": "RES-3", "repair_code": "RP-ELC-001",
                        "action": "Replace circuit breaker", "difficulty": "Moderate"},
    "diagnosis_complete": True, "severity": "High",
}
_DIAG_PHN = {
    "tree_id": "DT-PHN-001", "tree_name": "Phone Battery Not Charging",
    "symptom_code": "PRB-PHN-001", "category": "Phones",
    "repair_code": "RP-PHN-001", "recommended_action": "Replace phone battery",
    "resolution_path": {"path_id": "RES-3", "repair_code": "RP-PHN-001",
                        "action": "Replace phone battery", "difficulty": "Moderate"},
    "diagnosis_complete": True, "severity": "High",
}
_DIAG_LAP = {
    "tree_id": "DT-LAP-001", "tree_name": "Laptop Won't Turn On",
    "symptom_code": "PRB-LAP-001", "category": "Laptops",
    "repair_code": "RP-LAP-001", "recommended_action": "Replace thermal paste",
    "resolution_path": {"path_id": "RES-2", "repair_code": "RP-LAP-001",
                        "action": "Clean fan and replace thermal paste", "difficulty": "Moderate"},
    "diagnosis_complete": True, "severity": "High",
}
_DIAG_CAR = {
    "tree_id": "DT-CAR-001", "tree_name": "Check Engine Light",
    "symptom_code": "PRB-CAR-001", "category": "Cars",
    "repair_code": "RP-CAR-001", "recommended_action": "Replace O2 sensor",
    "resolution_path": {"path_id": "RES-1", "repair_code": "RP-CAR-001",
                        "action": "Replace oxygen sensor", "difficulty": "Easy"},
    "diagnosis_complete": True, "severity": "Variable",
}
_DIAG_HEQ = {
    "tree_id": "DT-HEQ-001", "tree_name": "Hydraulic System",
    "symptom_code": "PRB-HVY-001", "category": "Heavy Equipment",
    "repair_code": "RP-HEQ-001", "recommended_action": "Replace excavator track",
    "resolution_path": {"path_id": "RES-1", "repair_code": "RP-HEQ-001",
                        "action": "Replace excavator track", "difficulty": "Expert"},
    "diagnosis_complete": True, "severity": "High",
}
_DIAG_GEN = {
    "tree_id": "DT-GEN-001", "tree_name": "Generator Not Starting",
    "symptom_code": "PRB-GEN-001", "category": "Generators",
    "repair_code": "RP-GEN-001", "recommended_action": "Repair generator control panel",
    "resolution_path": {"path_id": "RES-3", "repair_code": "RP-GEN-001",
                        "action": "Repair generator control panel", "difficulty": "Expert"},
    "diagnosis_complete": True, "severity": "Critical",
}

VERSION_FIXTURES = {
    1: {
        "label": "Home Maintenance",
        "cases": [
            ("PRB-ROF-002", _DIAG_ROF, "RP-ROF-001"),
            ("PRB-PLM-002", _DIAG_PLB, "RP-PLB-001"),
            ("PRB-ELC-002", _DIAG_ELC, "RP-ELC-001"),
            ("PRB-HVC-001", {},         None),
        ],
        "parts_check_ids": ["RP-ROF-001", "RP-PLB-001", "RP-ELC-001", "RP-APL-001"],
        "plan_cases": [
            ("PRB-ROF-002", _DIAG_ROF),
            ("PRB-ELC-002", _DIAG_ELC),
            ("PRB-PLM-002", _DIAG_PLB),
        ],
    },
    2: {
        "label": "Electronics",
        "cases": [
            ("PRB-PHN-001", _DIAG_PHN, "RP-PHN-001"),
            ("PRB-PHN-002", {},         None),
            ("PRB-LAP-001", _DIAG_LAP, "RP-LAP-001"),
            ("PRB-DKT-001", {},         None),
        ],
        "parts_check_ids": ["RP-PHN-001", "RP-PHN-002", "RP-LAP-001", "RP-CON-001"],
        "plan_cases": [
            ("PRB-PHN-001", _DIAG_PHN),
            ("PRB-LAP-001", _DIAG_LAP),
            ("PRB-PHN-002", {}),
        ],
    },
    3: {
        "label": "Industrial / Automotive",
        "cases": [
            ("PRB-CAR-001", _DIAG_CAR, "RP-CAR-001"),
            ("PRB-HVY-001", _DIAG_HEQ, "RP-HEQ-001"),
            ("PRB-GEN-001", _DIAG_GEN, "RP-GEN-001"),
            ("PRB-MCY-001", {},         None),
        ],
        "parts_check_ids": ["RP-CAR-001", "RP-HEQ-001", "RP-GEN-001", "RP-SOL-001"],
        "plan_cases": [
            ("PRB-CAR-001", _DIAG_CAR),
            ("PRB-HVY-001", _DIAG_HEQ),
            ("PRB-GEN-001", _DIAG_GEN),
        ],
    },
}

# ===========================================================================
# Test functions
# ===========================================================================

# ---- engine lifecycle ----

def test_engine_loads(version: int, fx: dict) -> None:
    """Engine constructs and repr is sensible."""
    eng = AIRepairReasoningEngine(version=version)
    r = repr(eng)
    _assert("AIRepairReasoningEngine" in r, f"Bad repr: {r!r}")
    _assert(str(version) in r, f"Version not in repr: {r!r}")
    eng.close()


def test_context_manager(version: int, fx: dict) -> None:
    """Engine works as a context manager and closes cleanly."""
    with AIRepairReasoningEngine(version=version) as eng:
        recs = eng.recommend_repair(fx["cases"][0][0], fx["cases"][0][1])
        _assert(isinstance(recs, list), "recommend_repair must return a list")
    _assert(eng._db_conn is None, "DB connection not closed after __exit__")


# ---- recommend_repair ----

def test_recommend_repair_returns_results(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """
    recommend_repair always returns a list.
    When a direct repair_code is provided in the diagnostic result, at least
    one result must be returned (the matched repair).  Cases with an empty
    diagnostic dict and no direct code may legitimately return [] when the
    symptom prefix has no matching JSON repair — that is valid behaviour.
    """
    for symptom_code, diag, expected_id in fx["cases"]:
        recs = eng.recommend_repair(symptom_code, diag, top_k=5)
        _assert(isinstance(recs, list), f"Expected list for {symptom_code!r}")
        # Only enforce non-empty when we supplied a direct repair_code hint
        if expected_id:
            _assert(len(recs) > 0,
                    f"No recommendations for {symptom_code!r} "
                    f"(expected at least {expected_id!r})")


def test_recommend_repair_required_fields(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """Every recommendation dict contains all required keys."""
    required = {
        "rank", "id", "name", "category", "difficulty", "difficulty_score",
        "estimated_time", "estimated_time_minutes", "relevance_score",
        "match_reason", "tools_required", "materials_required",
        "safety_notes", "procedure_steps", "pre_repair_checks",
        "post_repair_checks", "warnings",
    }
    for symptom_code, diag, _ in fx["cases"]:
        recs = eng.recommend_repair(symptom_code, diag, top_k=5)
        for r in recs:
            for field in required:
                _assert(field in r,
                        f"Missing field {field!r} in rec for {symptom_code!r}")


def test_recommend_repair_rank_sequence(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """Ranks start at 1 and are sequential with no gaps."""
    for symptom_code, diag, _ in fx["cases"]:
        recs = eng.recommend_repair(symptom_code, diag, top_k=5)
        for i, r in enumerate(recs):
            _assert(r["rank"] == i + 1,
                    f"Rank {r['rank']} != {i+1} for {symptom_code!r}")


def test_recommend_repair_sorted_by_relevance(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """Results are sorted by descending relevance score."""
    for symptom_code, diag, _ in fx["cases"]:
        recs = eng.recommend_repair(symptom_code, diag, top_k=5)
        scores = [r["relevance_score"] for r in recs]
        _assert(scores == sorted(scores, reverse=True),
                f"Results not sorted by relevance for {symptom_code!r}: {scores}")


def test_recommend_repair_direct_code_is_first(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """When diagnostic_result has a repair_code, that repair must rank #1."""
    for symptom_code, diag, expected_id in fx["cases"]:
        if not expected_id:
            continue
        recs = eng.recommend_repair(symptom_code, diag, top_k=5)
        _assert(len(recs) > 0, f"No recs for {symptom_code!r}")
        _assert(recs[0]["id"] == expected_id,
                f"Expected {expected_id!r} at rank 1, got {recs[0]['id']!r}")


def test_recommend_repair_score_range(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """All relevance scores are in [0, 1]."""
    for symptom_code, diag, _ in fx["cases"]:
        for r in eng.recommend_repair(symptom_code, diag, top_k=5):
            _assert(0.0 <= r["relevance_score"] <= 1.0,
                    f"Score {r['relevance_score']} out of range for {symptom_code!r}")


def test_recommend_repair_difficulty_valid(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """Difficulty values are within the known set."""
    valid = {"Easy", "Moderate", "Hard", "Expert", "Variable"}
    for symptom_code, diag, _ in fx["cases"]:
        for r in eng.recommend_repair(symptom_code, diag, top_k=5):
            _assert(r["difficulty"] in valid,
                    f"Invalid difficulty {r['difficulty']!r} for {symptom_code!r}")


def test_recommend_repair_deterministic(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """Same inputs always produce identical results."""
    sym, diag, _ = fx["cases"][0]
    r1 = [x["id"] for x in eng.recommend_repair(sym, diag, top_k=5)]
    r2 = [x["id"] for x in eng.recommend_repair(sym, diag, top_k=5)]
    _assert(r1 == r2, f"Non-deterministic for {sym!r}: {r1} vs {r2}")


def test_recommend_repair_procedure_steps_nonempty(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """Top recommendation always has at least one procedure step."""
    for symptom_code, diag, expected_id in fx["cases"]:
        if not expected_id:
            continue
        recs = eng.recommend_repair(symptom_code, diag, top_k=1)
        _assert(len(recs) > 0, f"No recs for {symptom_code!r}")
        steps = recs[0]["procedure_steps"]
        _assert(isinstance(steps, list) and len(steps) > 0,
                f"procedure_steps empty for {symptom_code!r}")


# ---- check_parts_availability ----

def test_check_parts_returns_dict(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """check_parts_availability always returns a dict."""
    for rid in fx["parts_check_ids"]:
        result = eng.check_parts_availability(rid)
        _assert(isinstance(result, dict),
                f"Expected dict for {rid!r}, got {type(result)}")


def test_check_parts_required_keys(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """Parts availability dict contains all required top-level keys."""
    required = {
        "repair_id", "repair_name", "materials_needed",
        "parts", "total_parts_cost", "all_parts_available",
        "missing_parts", "low_stock_parts",
    }
    for rid in fx["parts_check_ids"]:
        result = eng.check_parts_availability(rid)
        for key in required:
            _assert(key in result,
                    f"Missing key {key!r} in parts check for {rid!r}")


def test_check_parts_cost_nonnegative(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """total_parts_cost is always >= 0."""
    for rid in fx["parts_check_ids"]:
        result = eng.check_parts_availability(rid)
        _assert(result["total_parts_cost"] >= 0,
                f"Negative total_parts_cost for {rid!r}")


def test_check_parts_status_valid(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """Every part entry has a valid status string."""
    valid_statuses = {"in_stock", "low_stock", "out_of_stock", "not_found"}
    for rid in fx["parts_check_ids"]:
        result = eng.check_parts_availability(rid)
        for p in result["parts"]:
            _assert(p["status"] in valid_statuses,
                    f"Invalid status {p['status']!r} for part in {rid!r}")


def test_check_parts_unknown_repair(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """Unknown repair_id returns graceful error dict, not an exception."""
    result = eng.check_parts_availability("RP-DOES-NOT-EXIST-999")
    _assert(isinstance(result, dict),          "Expected dict for unknown repair")
    _assert(result["all_parts_available"] is False,
            "Expected all_parts_available=False for unknown repair")
    _assert("error" in result or len(result["missing_parts"]) > 0,
            "Expected error or missing_parts for unknown repair")


def test_check_parts_materials_match(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """parts list length matches materials_needed length."""
    for rid in fx["parts_check_ids"]:
        result = eng.check_parts_availability(rid)
        _assert(
            len(result["parts"]) == len(result["materials_needed"]),
            f"parts({len(result['parts'])}) != materials_needed"
            f"({len(result['materials_needed'])}) for {rid!r}",
        )


# ---- generate_repair_plan ----

def test_generate_plan_returns_dict(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """generate_repair_plan always returns a dict."""
    for sym, diag in fx["plan_cases"]:
        plan = eng.generate_repair_plan(sym, diag)
        _assert(isinstance(plan, dict),
                f"Expected dict plan for {sym!r}")


def test_generate_plan_required_keys(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """Plan dict contains all required top-level keys."""
    required = {
        "symptom_code", "category", "diagnosis_summary",
        "primary_repair", "alternative_repairs",
        "total_estimated_time_minutes", "total_parts_cost",
        "all_parts_available", "difficulty", "urgency",
        "summary", "recommendations", "plan_steps",
    }
    for sym, diag in fx["plan_cases"]:
        plan = eng.generate_repair_plan(sym, diag)
        for key in required:
            _assert(key in plan,
                    f"Missing key {key!r} in plan for {sym!r}")


def test_generate_plan_summary_nonempty(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """summary string is always non-empty."""
    for sym, diag in fx["plan_cases"]:
        plan = eng.generate_repair_plan(sym, diag)
        _assert(bool(plan["summary"]),
                f"Empty summary for {sym!r}")


def test_generate_plan_time_nonnegative(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """total_estimated_time_minutes is >= 0."""
    for sym, diag in fx["plan_cases"]:
        plan = eng.generate_repair_plan(sym, diag)
        _assert(plan["total_estimated_time_minutes"] >= 0,
                f"Negative time for {sym!r}")


def test_generate_plan_cost_nonnegative(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """total_parts_cost is >= 0."""
    for sym, diag in fx["plan_cases"]:
        plan = eng.generate_repair_plan(sym, diag)
        _assert(plan["total_parts_cost"] >= 0,
                f"Negative cost for {sym!r}")


def test_generate_plan_steps_nonempty(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """plan_steps is a non-empty list when a primary repair is found."""
    for sym, diag in fx["plan_cases"]:
        plan = eng.generate_repair_plan(sym, diag)
        if plan["primary_repair"] is None:
            continue
        _assert(isinstance(plan["plan_steps"], list) and len(plan["plan_steps"]) > 0,
                f"plan_steps empty for {sym!r}")


def test_generate_plan_difficulty_valid(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """difficulty in plan is a valid string."""
    valid = {"Easy", "Moderate", "Hard", "Expert", "Variable", "Unknown"}
    for sym, diag in fx["plan_cases"]:
        plan = eng.generate_repair_plan(sym, diag)
        _assert(plan["difficulty"] in valid,
                f"Invalid difficulty {plan['difficulty']!r} for {sym!r}")


def test_generate_plan_urgency_valid(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """urgency in plan is a valid string."""
    valid = {"Immediate", "Urgent", "Normal", "Routine", "Unknown"}
    for sym, diag in fx["plan_cases"]:
        plan = eng.generate_repair_plan(sym, diag)
        _assert(plan["urgency"] in valid,
                f"Invalid urgency {plan['urgency']!r} for {sym!r}")


def test_generate_plan_primary_has_parts(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """primary_repair contains parts_availability sub-dict when repair is found."""
    for sym, diag in fx["plan_cases"]:
        plan = eng.generate_repair_plan(sym, diag)
        if plan["primary_repair"] is None:
            continue
        _assert("parts_availability" in plan["primary_repair"],
                f"primary_repair missing parts_availability for {sym!r}")


def test_generate_plan_alternatives_are_list(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """alternative_repairs is always a list."""
    for sym, diag in fx["plan_cases"]:
        plan = eng.generate_repair_plan(sym, diag)
        _assert(isinstance(plan["alternative_repairs"], list),
                f"alternative_repairs is not a list for {sym!r}")


def test_generate_plan_symptom_code_preserved(eng: AIRepairReasoningEngine, fx: dict) -> None:
    """plan['symptom_code'] equals the input symptom_code."""
    for sym, diag in fx["plan_cases"]:
        plan = eng.generate_repair_plan(sym, diag)
        _assert(plan["symptom_code"] == sym,
                f"symptom_code mismatch: {plan['symptom_code']!r} != {sym!r}")

# ===========================================================================
# Test runner
# ===========================================================================

_STANDALONE = [
    ("engine_loads",    test_engine_loads,    False),
    ("context_manager", test_context_manager, False),
]

_ENGINE_TESTS = [
    ("recommend_repair_returns_results",       test_recommend_repair_returns_results,       True),
    ("recommend_repair_required_fields",       test_recommend_repair_required_fields,       True),
    ("recommend_repair_rank_sequence",         test_recommend_repair_rank_sequence,         True),
    ("recommend_repair_sorted_by_relevance",   test_recommend_repair_sorted_by_relevance,   True),
    ("recommend_repair_direct_code_is_first",  test_recommend_repair_direct_code_is_first,  True),
    ("recommend_repair_score_range",           test_recommend_repair_score_range,           True),
    ("recommend_repair_difficulty_valid",      test_recommend_repair_difficulty_valid,      True),
    ("recommend_repair_deterministic",         test_recommend_repair_deterministic,         True),
    ("recommend_repair_steps_nonempty",        test_recommend_repair_procedure_steps_nonempty, True),
    ("check_parts_returns_dict",               test_check_parts_returns_dict,               True),
    ("check_parts_required_keys",              test_check_parts_required_keys,              True),
    ("check_parts_cost_nonnegative",           test_check_parts_cost_nonnegative,           True),
    ("check_parts_status_valid",               test_check_parts_status_valid,               True),
    ("check_parts_unknown_repair",             test_check_parts_unknown_repair,             True),
    ("check_parts_materials_match",            test_check_parts_materials_match,            True),
    ("generate_plan_returns_dict",             test_generate_plan_returns_dict,             True),
    ("generate_plan_required_keys",            test_generate_plan_required_keys,            True),
    ("generate_plan_summary_nonempty",         test_generate_plan_summary_nonempty,         True),
    ("generate_plan_time_nonnegative",         test_generate_plan_time_nonnegative,         True),
    ("generate_plan_cost_nonnegative",         test_generate_plan_cost_nonnegative,         True),
    ("generate_plan_steps_nonempty",           test_generate_plan_steps_nonempty,           True),
    ("generate_plan_difficulty_valid",         test_generate_plan_difficulty_valid,         True),
    ("generate_plan_urgency_valid",            test_generate_plan_urgency_valid,            True),
    ("generate_plan_primary_has_parts",        test_generate_plan_primary_has_parts,        True),
    ("generate_plan_alternatives_are_list",    test_generate_plan_alternatives_are_list,    True),
    ("generate_plan_symptom_code_preserved",   test_generate_plan_symptom_code_preserved,   True),
]

_ALL_TESTS = _STANDALONE + _ENGINE_TESTS


# pytest-compatible wrappers
def _make_pytest_fn(name, fn, needs_eng, version, fx):
    if needs_eng:
        def _t():
            with AIRepairReasoningEngine(version=version) as e:
                fn(e, fx)
    else:
        def _t():
            fn(version, fx)
    _t.__name__ = f"test_{name}_v{version}"
    return _t

for _v, _fx in VERSION_FIXTURES.items():
    for _name, _fn, _needs in _ALL_TESTS:
        _f = _make_pytest_fn(_name, _fn, _needs, _v, _fx)
        globals()[_f.__name__] = _f


def run_all_tests() -> None:
    total = passed = failed = 0

    for version, fx in VERSION_FIXTURES.items():
        print()
        print(_bold(f"{'='*62}"))
        print(_bold(f"  Version {version} – {fx['label']}"))
        print(_bold(f"{'='*62}"))

        try:
            engine = AIRepairReasoningEngine(version=version)
        except Exception as exc:
            print(_red(f"  FATAL: {exc}"))
            total  += len(_ALL_TESTS)
            failed += len(_ALL_TESTS)
            continue

        for test_name, test_fn, needs_engine in _ALL_TESTS:
            label = f"  {test_name:<45s}"
            total += 1
            try:
                if needs_engine:
                    test_fn(engine, fx)
                else:
                    test_fn(version, fx)
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

        engine.close()

    print()
    print(_bold("=" * 62))
    print(_bold(f"  Results: {passed}/{total} passed"))
    if failed:
        print(_red(f"  {failed} FAILED"))
    print(_bold("=" * 62))

    if failed:
        sys.exit(1)

# ===========================================================================
# Rich demo
# ===========================================================================

def run_demo() -> None:
    """Print a detailed walkthrough for all three versions."""
    demo_cases = {
        1: [
            ("PRB-ROF-002", _DIAG_ROF, "Roof Leak — shingles damaged"),
            ("PRB-ELC-002", _DIAG_ELC, "Dead electrical outlet"),
        ],
        2: [
            ("PRB-PHN-001", _DIAG_PHN, "iPhone battery not charging"),
            ("PRB-LAP-001", _DIAG_LAP, "Laptop overheating"),
        ],
        3: [
            ("PRB-CAR-001", _DIAG_CAR, "Check engine light — O2 sensor"),
            ("PRB-HVY-001", _DIAG_HEQ, "Excavator hydraulic system"),
        ],
    }

    for version, cases in demo_cases.items():
        fx = VERSION_FIXTURES[version]
        print()
        print(_cyan(_bold(f"{'#'*62}")))
        print(_cyan(_bold(f"  DEMO – Version {version}: {fx['label']}")))
        print(_cyan(_bold(f"{'#'*62}")))

        try:
            eng = AIRepairReasoningEngine(version=version)
        except Exception as exc:
            print(_red(f"  Could not load engine: {exc}"))
            continue

        for sym, diag, label in cases:
            print(_bold(f"\n  Symptom: {_yellow(sym)} — {label}"))

            # ── recommend_repair ──────────────────────────────────────
            recs = eng.recommend_repair(sym, diag, top_k=3)
            print(f"\n  {_bold('Recommendations')} (top {len(recs)}):")
            for r in recs:
                diff_colors = {
                    "Easy": _green, "Moderate": _yellow,
                    "Hard": _red,   "Expert": _red,
                }.get(r["difficulty"], str)
                print(
                    f"    {r['rank']:>2}. {_cyan(r['id']):<18s} "
                    f"{r['name']:<40s} "
                    f"{diff_colors(r['difficulty']):<10s} "
                    f"score={r['relevance_score']:.2f}  "
                    f"({r['estimated_time']})"
                )
                print(f"        reason: {r['match_reason']}")

            if not recs:
                print("    (no recommendations)")
                continue

            best = recs[0]

            # ── check_parts_availability ──────────────────────────────
            avail = eng.check_parts_availability(best["id"])
            print(f"\n  {_bold('Parts availability')} for {_cyan(best['id'])}:")
            for p in avail["parts"]:
                status_col = {"in_stock": _green, "low_stock": _yellow,
                              "out_of_stock": _red, "not_found": _red}.get(p["status"], str)
                cost_str = f"${p['unit_cost']:.2f}" if p["unit_cost"] is not None else "N/A"
                stock_str = str(p["current_stock"]) if p["current_stock"] is not None else "N/A"
                print(
                    f"    {status_col('● ' + p['status']):<22s} "
                    f"{p['material_name'][:38]:<40s} "
                    f"cost={cost_str:<10s} stock={stock_str}"
                )
                if p["part_name"]:
                    print(f"      ↳ {p['part_name']} ({p['supplier'] or 'N/A'}, "
                          f"{p['lead_time_days'] or '?'} days lead)")

            total_c = avail["total_parts_cost"]
            avail_flag = _green("ALL IN STOCK") if avail["all_parts_available"] \
                else _yellow(f"MISSING: {avail['missing_parts'][:2]}")
            print(f"    Total parts cost: ${total_c:.2f}  |  {avail_flag}")

            # ── generate_repair_plan ──────────────────────────────────
            plan = eng.generate_repair_plan(sym, diag, top_k=3)
            print(f"\n  {_bold('Repair Plan')}:")
            print(f"    Summary   : {_green(plan['summary'])}")
            print(f"    Difficulty: {plan['difficulty']}")
            print(f"    Time      : {plan['total_estimated_time_minutes']} min")
            print(f"    Cost      : ${plan['total_parts_cost']:.2f}")
            print(f"    Urgency   : {plan['urgency']}")

            if plan["alternative_repairs"]:
                alts = [f"{a['id']} ({a['difficulty']})" for a in plan["alternative_repairs"]]
                print(f"    Alternatives: {', '.join(alts)}")

            print(f"\n  {_bold('Ordered plan steps')}:")
            for step in plan["plan_steps"][:12]:
                print(f"    {step}")
            if len(plan["plan_steps"]) > 12:
                print(f"    … (+{len(plan['plan_steps'])-12} more steps)")

        eng.close()

    print()


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FixFinder Repair Reasoning Tests")
    parser.add_argument("--demo",       action="store_true", help="Rich demo output")
    parser.add_argument("--tests-only", action="store_true", help="Run tests without demo")
    args = parser.parse_args()

    if args.demo:
        run_demo()
    else:
        run_all_tests()
        if not args.tests_only:
            print()
            run_demo()
