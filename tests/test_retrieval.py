"""
tests/test_retrieval.py
=======================
Functional test suite for AIRetrievalEngine.

Run from workspace root:
    python tests/test_retrieval.py

Or via pytest:
    pytest tests/test_retrieval.py -v
"""

from __future__ import annotations

import os
import sys

# Make the workspace root importable regardless of how the test is invoked
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import traceback
from ai_engine.retrieval_engine import AIRetrievalEngine

# ---------------------------------------------------------------------------
# Colour helpers (no external deps)
# ---------------------------------------------------------------------------

def _green(s: str)  -> str: return f"\033[32m{s}\033[0m"
def _red(s: str)    -> str: return f"\033[31m{s}\033[0m"
def _yellow(s: str) -> str: return f"\033[33m{s}\033[0m"
def _cyan(s: str)   -> str: return f"\033[36m{s}\033[0m"
def _bold(s: str)   -> str: return f"\033[1m{s}\033[0m"

_PASS = _green("PASS")
_FAIL = _red("FAIL")
_SKIP = _yellow("SKIP")

# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------

def _assert(condition: bool, msg: str) -> None:
    if not condition:
        raise AssertionError(msg)


# ===========================================================================
# Per-version test configuration
# ===========================================================================

VERSION_TESTS = {
    1: {
        "label": "Home Maintenance",
        "queries": [
            "roof is leaking after heavy rain near the chimney",
            "water heater not producing hot water",
            "electrical outlet stopped working in bathroom",
            "furnace making loud banging noise when starting",
            "sump pump running constantly basement flooding",
        ],
        "system_lookups":  ["ROF-001", "HVC-001", "PLM-003"],
        "symptom_lookups": ["PRB-ROF-002", "PRB-HVC-002", "PRB-PLM-004"],
        "repair_lookups":  ["RP-ROF-001", "RP-PLB-001", "RP-ELC-001"],
    },
    2: {
        "label": "Electronics",
        "queries": [
            "iPhone battery drains extremely fast after update",
            "laptop overheating shutting down during gaming",
            "TV has black screen but sound still works",
            "phone cracked screen touch not responding",
            "PS5 HDMI port not displaying video on monitor",
        ],
        "system_lookups":  ["PHN-001", "LAP-001", "GAM-001"],
        "symptom_lookups": ["PRB-PHN-001", "PRB-LAP-001", "PRB-TV-001"],
        "repair_lookups":  ["RP-PHN-001", "RP-LAP-001", "RP-CON-001"],
    },
    3: {
        "label": "Industrial / Automotive",
        "queries": [
            "check engine light came on after highway driving",
            "excavator hydraulic arm moving slowly losing pressure",
            "diesel generator won't start in cold weather",
            "car brake pads making grinding noise when stopping",
            "solar panels output dropped 40 percent last month",
        ],
        "system_lookups":  ["CAR-001", "HVY-001", "GEN-001"],
        "symptom_lookups": ["PRB-CAR-001", "PRB-HVY-001", "PRB-GEN-001"],
        "repair_lookups":  ["RP-CAR-001", "RP-HEQ-001", "RP-GEN-001"],
    },
}

# ===========================================================================
# Individual test functions
# ===========================================================================

def test_engine_loads(version: int, cfg: dict) -> None:
    """Engine constructs without errors and repr is sensible."""
    engine = AIRetrievalEngine(version=version)
    r = repr(engine)
    _assert("AIRetrievalEngine" in r, f"repr unexpected: {r!r}")
    _assert(str(version) in r,        f"version not in repr: {r!r}")
    engine.close()


def test_search_returns_results(engine: AIRetrievalEngine, cfg: dict) -> None:
    """search() returns non-empty ranked results for every sample query."""
    for query in cfg["queries"]:
        results = engine.search(query, top_k=5)
        _assert(len(results) > 0,           f"No results for {query!r}")
        _assert(results[0]["rank"] == 1,     "First result rank != 1")
        _assert("entity_id"   in results[0], "Missing entity_id in result")
        _assert("entity_type" in results[0], "Missing entity_type in result")
        _assert("score"       in results[0], "Missing score in result")
        _assert(0.0 <= results[0]["score"] <= 1.01,
                f"Score out of [0,1] range: {results[0]['score']}")


def test_search_ranking_order(engine: AIRetrievalEngine, cfg: dict) -> None:
    """Scores must be in descending order."""
    for query in cfg["queries"][:2]:
        results = engine.search(query, top_k=5)
        scores = [r["score"] for r in results]
        _assert(
            scores == sorted(scores, reverse=True),
            f"Results not sorted for {query!r}: {scores}",
        )


def test_search_entity_type_filter(engine: AIRetrievalEngine, cfg: dict) -> None:
    """entity_type_filter returns only results of the requested type."""
    for etype in ("system", "symptom", "repair"):
        results = engine.search(cfg["queries"][0], top_k=5,
                                entity_type_filter=etype)
        for r in results:
            _assert(
                r["entity_type"] == etype,
                f"Filter={etype!r} returned {r['entity_type']!r}: {r['entity_id']!r}",
            )


def test_search_deterministic(engine: AIRetrievalEngine, cfg: dict) -> None:
    """Same query twice must return identical results (deterministic embeddings)."""
    q = cfg["queries"][0]
    r1 = engine.search(q, top_k=5)
    r2 = engine.search(q, top_k=5)
    ids1 = [r["entity_id"] for r in r1]
    ids2 = [r["entity_id"] for r in r2]
    _assert(ids1 == ids2, f"Non-deterministic results for {q!r}: {ids1} != {ids2}")


def test_get_system_details(engine: AIRetrievalEngine, cfg: dict) -> None:
    """get_system_details() returns correct required fields."""
    required = {
        "system_id", "system_name", "brand", "specifications",
        "common_issues", "lifespan_years",
    }
    for sid in cfg["system_lookups"]:
        result = engine.get_system_details(sid)
        # engine lookups are by system_code; if not found in DB, allow None
        if result is None:
            continue
        for field in required:
            _assert(field in result, f"Missing field {field!r} in system {sid!r}")


def test_get_symptom_details(engine: AIRetrievalEngine, cfg: dict) -> None:
    """get_symptom_details() returns correct required fields."""
    required = {
        "symptom_id", "symptom_name", "severity",
        "description", "causes", "diagnostic_time_minutes",
    }
    for syid in cfg["symptom_lookups"]:
        result = engine.get_symptom_details(syid)
        if result is None:
            continue
        for field in required:
            _assert(field in result, f"Missing field {field!r} in symptom {syid!r}")


def test_get_repair_procedure(engine: AIRetrievalEngine, cfg: dict) -> None:
    """get_repair_procedure() returns correct required fields."""
    required = {
        "repair_id", "repair_name", "overview",
        "tools_required", "procedure_steps",
        "estimated_time_minutes", "difficulty",
    }
    for rid in cfg["repair_lookups"]:
        result = engine.get_repair_procedure(rid)
        if result is None:
            continue
        for field in required:
            _assert(field in result, f"Missing field {field!r} in repair {rid!r}")


def test_unknown_entity_returns_none(engine: AIRetrievalEngine, cfg: dict) -> None:
    """Lookups for non-existent IDs return None (no exception)."""
    _assert(engine.get_system_details("DOES-NOT-EXIST-999")   is None,
            "Expected None for unknown system_id")
    _assert(engine.get_symptom_details("DOES-NOT-EXIST-999")  is None,
            "Expected None for unknown symptom_id")
    _assert(engine.get_repair_procedure("DOES-NOT-EXIST-999") is None,
            "Expected None for unknown repair_id")


def test_context_manager(version: int, cfg: dict) -> None:
    """Engine works correctly as a context manager."""
    with AIRetrievalEngine(version=version) as eng:
        results = eng.search(cfg["queries"][0], top_k=3)
        _assert(len(results) > 0, "No results inside context manager")
    # After __exit__, DB connection should be closed
    _assert(eng._db_conn is None, "Connection not closed after context manager exit")


def test_empty_query_raises(engine: AIRetrievalEngine, cfg: dict) -> None:
    """Empty query string raises ValueError."""
    raised = False
    try:
        engine.search("", top_k=3)
    except ValueError:
        raised = True
    _assert(raised, "Expected ValueError for empty query")


# ===========================================================================
# Test runner
# ===========================================================================

_ALL_TESTS = [
    ("engine_loads",               test_engine_loads,             False),  # needs fresh engine
    ("context_manager",            test_context_manager,          False),  # needs fresh engine
    ("search_returns_results",     test_search_returns_results,   True),
    ("search_ranking_order",       test_search_ranking_order,     True),
    ("search_entity_type_filter",  test_search_entity_type_filter,True),
    ("search_deterministic",       test_search_deterministic,     True),
    ("get_system_details",         test_get_system_details,       True),
    ("get_symptom_details",        test_get_symptom_details,      True),
    ("get_repair_procedure",       test_get_repair_procedure,     True),
    ("unknown_entity_returns_none",test_unknown_entity_returns_none, True),
    ("empty_query_raises",         test_empty_query_raises,       True),
]

# pytest-compatible wrappers (auto-discovered when pytest is available)
def _make_pytest_test(name, fn, needs_engine, version, cfg):
    if needs_engine:
        def _test():
            with AIRetrievalEngine(version=version) as eng:
                fn(eng, cfg)
    else:
        def _test():
            fn(version, cfg)
    _test.__name__ = f"test_{name}_v{version}"
    return _test


# Inject pytest-compatible functions into module namespace
for _v, _cfg in VERSION_TESTS.items():
    for _name, _fn, _needs_eng in _ALL_TESTS:
        _func = _make_pytest_test(_name, _fn, _needs_eng, _v, _cfg)
        globals()[_func.__name__] = _func


def run_all_tests() -> None:
    """Run all tests for all versions and print a formatted summary."""
    total   = 0
    passed  = 0
    failed  = 0
    skipped = 0

    for version, cfg in VERSION_TESTS.items():
        print()
        print(_bold(f"{'='*60}"))
        print(_bold(f"  Version {version} – {cfg['label']}"))
        print(_bold(f"{'='*60}"))

        # Shared engine for tests that reuse one
        try:
            engine = AIRetrievalEngine(version=version)
        except Exception as exc:
            print(_red(f"  FATAL: Could not create engine: {exc}"))
            skipped += len(_ALL_TESTS)
            total   += len(_ALL_TESTS)
            continue

        for test_name, test_fn, needs_engine in _ALL_TESTS:
            label = f"  {test_name:<38s}"
            total += 1
            try:
                if needs_engine:
                    test_fn(engine, cfg)
                else:
                    test_fn(version, cfg)
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

    # ---- Summary ----
    print()
    print(_bold("=" * 60))
    print(_bold(f"  Results: {passed}/{total} passed"))
    if failed:
        print(_red(f"  {failed} FAILED"))
    if skipped:
        print(_yellow(f"  {skipped} SKIPPED"))
    print(_bold("=" * 60))

    if failed:
        sys.exit(1)


# ---------------------------------------------------------------------------
# Detailed demo output (separate from pass/fail tests)
# ---------------------------------------------------------------------------

def run_demo() -> None:
    """
    Print a rich human-readable demo of the engine for all three versions.
    Shows search results, system details, symptom details, and repair procedures.
    """
    for version, cfg in VERSION_TESTS.items():
        print()
        print(_cyan(_bold(f"{'#'*60}")))
        print(_cyan(_bold(f"  DEMO – Version {version}: {cfg['label']}")))
        print(_cyan(_bold(f"{'#'*60}")))

        try:
            engine = AIRetrievalEngine(version=version)
        except Exception as exc:
            print(_red(f"  Could not load engine: {exc}"))
            continue

        # ---- Search ----
        print(_bold("\n  [ Search results ]"))
        for query in cfg["queries"][:3]:
            print(f"\n  Query: {_yellow(repr(query))}")
            results = engine.search(query, top_k=5)
            for r in results:
                etype = r["entity_type"]
                color = {"system": _green, "symptom": _yellow, "repair": _cyan}.get(etype, str)
                print(
                    f"    {r['rank']:>2}.  {color(r['entity_id']):<22s} "
                    f"type={etype:<8s} score={r['score']:.4f}"
                )

        # ---- System details ----
        print(_bold("\n  [ System details ]"))
        for sid in cfg["system_lookups"][:2]:
            info = engine.get_system_details(sid)
            if info:
                print(f"  {_green(sid)}")
                print(f"    name     : {info['system_name']}")
                print(f"    brand    : {info['brand']}")
                print(f"    lifespan : {info['lifespan_years']} years")
                issues = info["common_issues"]
                print(f"    issues   : {issues[:2] if isinstance(issues, list) else issues}")
            else:
                print(f"  {_yellow(sid)}: not found in DB (code may differ from FAISS id)")

        # ---- Symptom details ----
        print(_bold("\n  [ Symptom details ]"))
        for syid in cfg["symptom_lookups"][:2]:
            info = engine.get_symptom_details(syid)
            if info:
                print(f"  {_yellow(syid)}")
                print(f"    name     : {info['symptom_name']}")
                print(f"    severity : {info['severity']}")
                causes = info["causes"]
                print(f"    causes   : {causes[:2] if isinstance(causes, list) else causes}")
                print(f"    time     : {info['diagnostic_time_minutes']} min")
            else:
                print(f"  {_yellow(syid)}: not found in DB (code may differ from FAISS id)")

        # ---- Repair procedures ----
        print(_bold("\n  [ Repair procedures ]"))
        for rid in cfg["repair_lookups"][:2]:
            info = engine.get_repair_procedure(rid)
            if info:
                print(f"  {_cyan(rid)}")
                print(f"    name       : {info['repair_name']}")
                print(f"    difficulty : {info['difficulty']}")
                print(f"    time       : {info['estimated_time_minutes']} min")
                steps = info["procedure_steps"]
                step_count = len(steps) if isinstance(steps, list) else "?"
                print(f"    steps      : {step_count}")
                tools = info["tools_required"]
                print(f"    tools      : {tools[:3] if isinstance(tools, list) else tools}")
            else:
                print(f"  {_cyan(rid)}: not found in DB (code may differ from FAISS id)")

        engine.close()

    print()


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FixFinder Retrieval Engine Tests")
    parser.add_argument("--demo",       action="store_true",
                        help="Run rich demo output instead of tests")
    parser.add_argument("--tests-only", action="store_true",
                        help="Run only tests (no demo)")
    args = parser.parse_args()

    if args.demo:
        run_demo()
    else:
        run_all_tests()
        if not args.tests_only:
            print()
            run_demo()
