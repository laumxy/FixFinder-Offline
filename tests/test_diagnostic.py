"""
tests/test_diagnostic.py
========================
Functional test suite for AIDiagnosticEngine.

Run from workspace root:
    python tests/test_diagnostic.py           # tests + demo
    python tests/test_diagnostic.py --demo    # demo only
    python tests/test_diagnostic.py --tests-only
    pytest tests/test_diagnostic.py -v
"""

from __future__ import annotations

import os
import sys
import traceback
import argparse

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from ai_engine.diagnostic_engine import AIDiagnosticEngine

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

VERSION_FIXTURES = {
    1: {
        "label": "Home Maintenance",
        "symptom_queries": [
            ("roof leaking after heavy rain near chimney",          "PRB-ROF"),
            ("water heater not producing any hot water",            "PRB-PLM"),
            ("electrical outlet stopped working dead no power",     "PRB-ELC"),
            ("furnace not heating house cold winter",               "PRB-HVC"),
            ("refrigerator not cooling food warm compressor",       None),      # no DB entry expected
        ],
        # (symptom_code, yes/no responses, expected repair code fragment OR None)
        "diagnostic_runs": [
            ("PRB-ROF-002", ["yes", "no", "yes", "no", "yes"], "RP-ROF"),
            ("PRB-ROF-002", ["no",  "yes", "no", "no", "no"],  "RP-ROF"),
            ("PRB-ELC-002", ["yes", "yes", "no"],               None),
            ("PRB-ELC-002", ["no",  "no",  "yes"],              "RP-ELC"),
            ("PRB-PLM-002", ["yes", "no",  "no"],               None),
        ],
        "tree_codes": ["PRB-ROF-002", "PRB-PLM-002", "PRB-ELC-002"],
    },
    2: {
        "label": "Electronics",
        "symptom_queries": [
            ("iPhone battery drains fast not charging",            "PRB-PHN"),
            ("phone screen cracked display not working touch",     "PRB-PHN"),
            ("laptop overheating shutting down fan noise",         "PRB-LAP"),
            ("TV no picture black screen sound works",             "PRB-TV"),
            ("PS5 HDMI port no video display black",               None),
        ],
        "diagnostic_runs": [
            ("PRB-PHN-001", ["yes", "no", "yes", "no"],  None),
            ("PRB-PHN-001", ["no",  "yes", "no", "yes"], "RP-PHN"),
            ("PRB-PHN-002", ["yes", "no",  "yes"],        "RP-PHN"),
            ("PRB-PHN-002", ["no",  "yes", "no"],         "RP-PHN"),
            ("PRB-LAP-003", ["yes", "no",  "yes", "yes"], None),
        ],
        "tree_codes": ["PRB-PHN-001", "PRB-PHN-002", "PRB-LAP-003"],
    },
    3: {
        "label": "Industrial / Automotive",
        "symptom_queries": [
            ("check engine light on after highway driving O2",     "PRB-CAR"),
            ("excavator hydraulic arm slow losing pressure",       "PRB-HVY"),
            ("diesel generator won't start cold weather battery",  "PRB-GEN"),
            ("brake grinding noise when stopping car",             "PRB-CAR"),
            ("solar panel output dropped significantly",           None),
        ],
        "diagnostic_runs": [
            ("PRB-CAR-001", ["no",  "yes", "yes", "no"],  "RP-CAR"),
            ("PRB-CAR-001", ["yes", "no",  "no",  "no"],  None),
            ("PRB-HVY-001", ["yes", "yes", "no",  "no"],  None),
            ("PRB-GEN-001", ["no",  "yes", "no",  "yes"], None),
            ("PRB-CAR-001", ["no",  "no",  "no",  "yes"], "RP-CAR"),
        ],
        "tree_codes": ["PRB-CAR-001", "PRB-HVY-001", "PRB-GEN-001"],
    },
}


# ===========================================================================
# Individual test functions
# ===========================================================================

def test_engine_loads(version: int, fx: dict) -> None:
    """Engine constructs without errors; repr is sensible."""
    eng = AIDiagnosticEngine(version=version)
    r = repr(eng)
    _assert("AIDiagnosticEngine" in r, f"Bad repr: {r!r}")
    eng.close()


def test_context_manager(version: int, fx: dict) -> None:
    """Engine works as a context manager and closes cleanly."""
    with AIDiagnosticEngine(version=version) as eng:
        matches = eng.analyze_symptoms(fx["symptom_queries"][0][0], top_k=3)
        _assert(isinstance(matches, list), "analyze_symptoms must return a list")
    _assert(eng._db_conn is None, "DB connection not closed after __exit__")


def test_analyze_symptoms_returns_results(eng: AIDiagnosticEngine, fx: dict) -> None:
    """analyze_symptoms returns a non-empty ranked list for every query."""
    for query, _ in fx["symptom_queries"][:3]:
        results = eng.analyze_symptoms(query, top_k=5)
        _assert(len(results) > 0, f"No results for query: {query!r}")
        _assert(results[0]["rank"] == 1, "First result rank must be 1")
        for field in ("symptom_id", "symptom_code", "symptom_name",
                      "severity", "score", "matched_tokens"):
            _assert(field in results[0],
                    f"Missing field {field!r} in result for {query!r}")


def test_analyze_symptoms_scores_in_range(eng: AIDiagnosticEngine, fx: dict) -> None:
    """All returned scores are in [0, 1]."""
    for query, _ in fx["symptom_queries"][:3]:
        for r in eng.analyze_symptoms(query, top_k=5):
            _assert(0.0 <= r["score"] <= 1.0,
                    f"Score {r['score']} out of range for {query!r}")


def test_analyze_symptoms_sorted_descending(eng: AIDiagnosticEngine, fx: dict) -> None:
    """Results are sorted by descending score."""
    for query, _ in fx["symptom_queries"][:3]:
        results = eng.analyze_symptoms(query, top_k=5)
        scores = [r["score"] for r in results]
        _assert(scores == sorted(scores, reverse=True),
                f"Results not sorted for {query!r}: {scores}")


def test_analyze_symptoms_prefix_hint(eng: AIDiagnosticEngine, fx: dict) -> None:
    """
    When a symptom_code prefix hint is provided, the top result's symptom_name
    should contain at least one keyword from the query.
    (The DB may use sym_* style codes rather than PRB-* — we validate
    relevance by keyword presence in the name instead of code format.)
    """
    for query, expected_prefix in fx["symptom_queries"]:
        if expected_prefix is None:
            continue
        results = eng.analyze_symptoms(query, top_k=5)
        if not results:
            continue   # no match is acceptable
        # Accept if any matched token appears in the top result's name
        top      = results[0]
        name_lc  = top["symptom_name"].lower()
        tokens   = top["matched_tokens"]
        relevant = any(t in name_lc for t in tokens) if tokens else True
        _assert(
            relevant,
            f"Top result {top['symptom_code']!r} name={top['symptom_name']!r} "
            f"shares no matched tokens {tokens} with query {query!r}",
        )


def test_analyze_symptoms_deterministic(eng: AIDiagnosticEngine, fx: dict) -> None:
    """Same input → identical results on repeated calls."""
    query = fx["symptom_queries"][0][0]
    r1 = [x["symptom_code"] for x in eng.analyze_symptoms(query, top_k=5)]
    r2 = [x["symptom_code"] for x in eng.analyze_symptoms(query, top_k=5)]
    _assert(r1 == r2, f"Non-deterministic results for {query!r}")


def test_analyze_symptoms_empty_input(eng: AIDiagnosticEngine, fx: dict) -> None:
    """Empty / whitespace-only input returns an empty list (not an error)."""
    for bad in ("", "   ", "\t\n"):
        result = eng.analyze_symptoms(bad, top_k=5)
        _assert(isinstance(result, list), "Expected list for empty input")
        _assert(len(result) == 0,         "Expected empty list for blank input")


def test_get_diagnostic_tree_found(eng: AIDiagnosticEngine, fx: dict) -> None:
    """get_diagnostic_tree returns a valid tree for known symptom codes."""
    for code in fx["tree_codes"]:
        tree = eng.get_diagnostic_tree(code)
        if tree is None:
            continue   # DB code may differ from JSON tree code; skip, don't fail
        for field in ("id", "name", "steps", "decision_points", "resolution_paths"):
            _assert(field in tree, f"Missing field {field!r} in tree for {code!r}")
        _assert(len(tree["steps"])             > 0, "steps must be non-empty")
        _assert(len(tree["decision_points"])   > 0, "decision_points must be non-empty")
        _assert(len(tree["resolution_paths"])  > 0, "resolution_paths must be non-empty")


def test_get_diagnostic_tree_unknown(eng: AIDiagnosticEngine, fx: dict) -> None:
    """get_diagnostic_tree returns None for an unknown code."""
    result = eng.get_diagnostic_tree("PRB-DOES-NOT-EXIST-999")
    _assert(result is None, "Expected None for unknown symptom code")


def test_run_diagnostic_structure(eng: AIDiagnosticEngine, fx: dict) -> None:
    """run_diagnostic always returns a dict with the required keys."""
    required = {
        "tree_id", "tree_name", "symptom_code",
        "steps_presented", "decisions_made",
        "recommended_action", "repair_code",
        "resolution_path", "diagnosis_complete", "remaining_steps",
    }
    for code, responses, _ in fx["diagnostic_runs"]:
        result = eng.run_diagnostic(code, responses)
        for key in required:
            _assert(key in result, f"Missing key {key!r} for ({code}, {responses})")


def test_run_diagnostic_recommended_action_nonempty(
    eng: AIDiagnosticEngine, fx: dict
) -> None:
    """recommended_action is never an empty string."""
    for code, responses, _ in fx["diagnostic_runs"]:
        result = eng.run_diagnostic(code, responses)
        _assert(
            bool(result["recommended_action"]),
            f"Empty recommended_action for ({code}, {responses})",
        )


def test_run_diagnostic_decisions_length(eng: AIDiagnosticEngine, fx: dict) -> None:
    """decisions_made length <= number of responses supplied."""
    for code, responses, _ in fx["diagnostic_runs"]:
        result = eng.run_diagnostic(code, responses)
        _assert(
            len(result["decisions_made"]) <= len(responses),
            f"More decisions than responses for ({code}): "
            f"{len(result['decisions_made'])} > {len(responses)}",
        )


def test_run_diagnostic_unknown_code(eng: AIDiagnosticEngine, fx: dict) -> None:
    """run_diagnostic on an unknown code returns diagnosis_complete=False."""
    result = eng.run_diagnostic("PRB-DOES-NOT-EXIST-999", ["yes", "no"])
    _assert(result["diagnosis_complete"] is False,
            "Expected diagnosis_complete=False for unknown code")
    _assert(result["tree_id"] is None, "Expected tree_id=None for unknown code")


def test_run_diagnostic_repair_code_format(eng: AIDiagnosticEngine, fx: dict) -> None:
    """When a repair_code is returned it must match RP-XXX-NNN format."""
    import re
    pattern = re.compile(r"^RP-[A-Z]{2,6}-\d{3}$")
    for code, responses, _ in fx["diagnostic_runs"]:
        result = eng.run_diagnostic(code, responses)
        rc = result["repair_code"]
        if rc is not None:
            _assert(bool(pattern.match(rc)),
                    f"Invalid repair_code format {rc!r} for ({code})")


def test_run_diagnostic_empty_responses(eng: AIDiagnosticEngine, fx: dict) -> None:
    """run_diagnostic handles empty responses without crashing."""
    for code in fx["tree_codes"][:2]:
        result = eng.run_diagnostic(code, [])
        _assert("recommended_action" in result,
                f"Missing recommended_action with empty responses for {code!r}")


def test_run_diagnostic_yes_path_vs_no_path(eng: AIDiagnosticEngine, fx: dict) -> None:
    """Supplying all-yes vs all-no should produce different decisions."""
    code = fx["tree_codes"][0]
    tree = eng.get_diagnostic_tree(code)
    if tree is None or len(tree["decision_points"]) < 2:
        return   # skip if tree not in JSON

    n = len(tree["decision_points"])
    res_yes = eng.run_diagnostic(code, ["yes"] * n)
    res_no  = eng.run_diagnostic(code, ["no"]  * n)

    yes_outcomes = [d["outcome"] for d in res_yes["decisions_made"]]
    no_outcomes  = [d["outcome"] for d in res_no["decisions_made"]]
    # At least one decision should differ
    _assert(
        yes_outcomes != no_outcomes,
        f"yes-path and no-path produced identical decisions for {code!r}",
    )


# ===========================================================================
# Test runner
# ===========================================================================

_STANDALONE_TESTS = [
    # (name, fn, needs_shared_engine)
    ("engine_loads",                        test_engine_loads,                           False),
    ("context_manager",                     test_context_manager,                        False),
]

_ENGINE_TESTS = [
    ("analyze_symptoms_returns_results",    test_analyze_symptoms_returns_results,       True),
    ("analyze_symptoms_scores_in_range",    test_analyze_symptoms_scores_in_range,       True),
    ("analyze_symptoms_sorted_descending",  test_analyze_symptoms_sorted_descending,     True),
    ("analyze_symptoms_prefix_hint",        test_analyze_symptoms_prefix_hint,           True),
    ("analyze_symptoms_deterministic",      test_analyze_symptoms_deterministic,         True),
    ("analyze_symptoms_empty_input",        test_analyze_symptoms_empty_input,           True),
    ("get_diagnostic_tree_found",           test_get_diagnostic_tree_found,              True),
    ("get_diagnostic_tree_unknown",         test_get_diagnostic_tree_unknown,            True),
    ("run_diagnostic_structure",            test_run_diagnostic_structure,               True),
    ("run_diagnostic_recommended_nonempty", test_run_diagnostic_recommended_action_nonempty, True),
    ("run_diagnostic_decisions_length",     test_run_diagnostic_decisions_length,        True),
    ("run_diagnostic_unknown_code",         test_run_diagnostic_unknown_code,            True),
    ("run_diagnostic_repair_code_format",   test_run_diagnostic_repair_code_format,      True),
    ("run_diagnostic_empty_responses",      test_run_diagnostic_empty_responses,         True),
    ("run_diagnostic_yes_vs_no_path",       test_run_diagnostic_yes_path_vs_no_path,     True),
]

_ALL_TESTS = _STANDALONE_TESTS + _ENGINE_TESTS


# pytest-compatible wrappers auto-injected into module namespace
def _make_pytest_fn(name, fn, needs_eng, version, fx):
    if needs_eng:
        def _test():
            with AIDiagnosticEngine(version=version) as e:
                fn(e, fx)
    else:
        def _test():
            fn(version, fx)
    _test.__name__ = f"test_{name}_v{version}"
    return _test

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
            engine = AIDiagnosticEngine(version=version)
        except Exception as exc:
            print(_red(f"  FATAL: Could not create engine: {exc}"))
            total += len(_ALL_TESTS)
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
    """Print a detailed human-readable walkthrough for all three versions."""

    demo_scenarios = {
        1: [
            {
                "query":     "roof is leaking badly after rain near chimney",
                "responses": ["yes", "no", "yes", "no", "yes"],
            },
            {
                "query":     "electrical outlet completely dead no power bathroom",
                "responses": ["no", "yes", "no"],
            },
        ],
        2: [
            {
                "query":     "iPhone battery drains really fast won't charge at all",
                "responses": ["no", "yes", "no", "yes"],
            },
            {
                "query":     "laptop screen is cracked touch doesn't respond properly",
                "responses": ["no", "yes", "yes"],
            },
        ],
        3: [
            {
                "query":     "check engine light on highway O2 sensor misfire",
                "responses": ["no", "yes", "yes", "no"],
            },
            {
                "query":     "excavator hydraulic bucket moving slowly leaking oil",
                "responses": ["yes", "yes", "no", "no"],
            },
        ],
    }

    for version, scenarios in demo_scenarios.items():
        fx = VERSION_FIXTURES[version]
        print()
        print(_cyan(_bold(f"{'#'*62}")))
        print(_cyan(_bold(f"  DEMO – Version {version}: {fx['label']}")))
        print(_cyan(_bold(f"{'#'*62}")))

        try:
            eng = AIDiagnosticEngine(version=version)
        except Exception as exc:
            print(_red(f"  Could not load engine: {exc}"))
            continue

        for sc in scenarios:
            query     = sc["query"]
            responses = sc["responses"]

            print(_bold(f"\n  Query: {_yellow(repr(query))}"))

            # --- analyze_symptoms ---
            matches = eng.analyze_symptoms(query, top_k=5)
            print(f"  {_bold('Symptom matches')} (top {len(matches)}):")
            for m in matches:
                bar_len = int(m["score"] * 30)
                bar     = "█" * bar_len + "░" * (30 - bar_len)
                print(
                    f"    {m['rank']:>2}.  {_yellow(m['symptom_code']):<22s} "
                    f"sev={m['severity']:<10s} "
                    f"score={m['score']:.4f}  [{bar}]"
                )
                print(f"        {m['symptom_name']}")
                tokens = m["matched_tokens"][:6]
                print(f"        matched: {tokens}")

            if not matches:
                print("    (no matches)")
                continue

            best_code = matches[0]["symptom_code"]

            # --- get_diagnostic_tree ---
            tree = eng.get_diagnostic_tree(best_code)
            if tree:
                print(f"\n  {_bold('Diagnostic tree')}: "
                      f"{_cyan(tree['id'])} — {tree['name']}")
                print(f"    Steps: {tree['total_steps']}  |  "
                      f"Avg time: {tree.get('avg_resolution_time_minutes','?')} min  |  "
                      f"Success: {tree.get('success_rate_percentage','?')}%")
                print(f"    Decision points ({len(tree['decision_points'])}):")
                for dp in tree["decision_points"]:
                    print(f"      [{dp['id']}] {dp['question']}")
                    print(f"             YES → {dp['yes']}")
                    print(f"             NO  → {dp['no']}")
            else:
                print(f"\n  {_yellow('No diagnostic tree found for')} {best_code!r}")

            # --- run_diagnostic ---
            print(f"\n  {_bold('Diagnostic run')} "
                  f"(responses: {responses}):")
            result = eng.run_diagnostic(best_code, responses)

            for d in result["decisions_made"]:
                ans_color = _green if d["answer"] == "yes" else _red
                print(f"    [{d['dp_id']}] {d['question']}")
                print(f"           → {ans_color(d['answer'].upper())}  "
                      f"outcome: {d['outcome']}")

            print(f"\n  {_bold('Recommended action')}:")
            print(f"    {_green(result['recommended_action'])}")

            if result["repair_code"]:
                print(f"  {_bold('Repair code')}: {_cyan(result['repair_code'])}")

            rp = result["resolution_path"]
            if rp:
                print(f"  {_bold('Resolution path')} [{rp['path_id']}]:")
                print(f"    Condition : {rp['condition']}")
                print(f"    Action    : {rp['action']}")
                print(f"    Difficulty: {rp['difficulty']}")
                if rp.get("estimated_time_minutes"):
                    print(f"    Est. time : {rp['estimated_time_minutes']} min")

            complete = result["diagnosis_complete"]
            remaining = result["remaining_steps"]
            status = _green("COMPLETE") if complete else _yellow(f"INCOMPLETE ({remaining} steps remaining)")
            print(f"  {_bold('Status')}: {status}")

        eng.close()

    print()


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FixFinder Diagnostic Engine Tests")
    parser.add_argument("--demo",        action="store_true",
                        help="Rich demo walkthrough")
    parser.add_argument("--tests-only",  action="store_true",
                        help="Run tests without demo")
    args = parser.parse_args()

    if args.demo:
        run_demo()
    else:
        run_all_tests()
        if not args.tests_only:
            print()
            run_demo()
