"""
scripts/master_build.py
========================
FixFinder Master Build Script.

Runs all data-pipeline and AI-engine phases in order for one or all
three FixFinder versions, then validates the result and prints a final
summary report.

Build phases
------------
  1  Master Taxonomy       – skipped (manually authored)
  2  Database Schema       – directories + SQLite schema confirmed present
  3  SQLite Database       – confirms DB files exist and are non-empty
  4  CSV Generation        – runs generate_csvs.py
  5  JSON Generation       – runs generate_jsons.py
  6  Embedding Generation  – runs generate_embeddings.py
  7  FAISS Index           – runs build_faiss_indices.py
  8  AI Retrieval Tests    – runs tests/test_retrieval.py
  9  AI Diagnostic Tests   – runs tests/test_diagnostic.py
 10  AI Repair Tests       – runs tests/test_repair_reasoning.py
 11  Validation Suite      – runs scripts/validation_suite.py

Usage
-----
    # Build + test all three versions
    python scripts/master_build.py

    # Single version only
    python scripts/master_build.py --version 1

    # Skip tests (phases 8-10)
    python scripts/master_build.py --skip-tests

    # Dry-run: print what would run without executing
    python scripts/master_build.py --dry-run

    # Force-rebuild even if artefacts already exist
    python scripts/master_build.py --force

    # Show final summary only
    python scripts/master_build.py --summary-only
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Root resolution — works whether invoked from workspace root or scripts/
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
_ROOT       = _SCRIPT_DIR.parent

# Ensure workspace root is on sys.path so ai_engine imports work
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt = "%H:%M:%S",
    handlers= [logging.StreamHandler(sys.stdout)],
)
# Force UTF-8 on Windows stdout so log lines don't corrupt
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
log = logging.getLogger("master_build")

# ---------------------------------------------------------------------------
# Colour helpers (gracefully degrades on Windows without ANSI support)
# ---------------------------------------------------------------------------

_USE_COLOUR = sys.stdout.isatty()

def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOUR else text

def _green(s: str)  -> str: return _c(s, "32")
def _red(s: str)    -> str: return _c(s, "31")
def _yellow(s: str) -> str: return _c(s, "33")
def _cyan(s: str)   -> str: return _c(s, "36")
def _bold(s: str)   -> str: return _c(s, "1")
def _dim(s: str)    -> str: return _c(s, "2")

# ---------------------------------------------------------------------------
# Phase result dataclass
# ---------------------------------------------------------------------------

class PhaseResult:
    """Holds the outcome of one build phase."""

    def __init__(
        self,
        phase_num:   int,
        phase_name:  str,
        status:      str,           # PASS | FAIL | SKIP | WARN
        duration_s:  float = 0.0,
        message:     str   = "",
        detail:      str   = "",
    ) -> None:
        self.phase_num  = phase_num
        self.phase_name = phase_name
        self.status     = status
        self.duration_s = duration_s
        self.message    = message
        self.detail     = detail

    @property
    def passed(self) -> bool:
        return self.status in ("PASS", "SKIP", "WARN")

    def to_dict(self) -> dict:
        return {
            "phase":      self.phase_num,
            "name":       self.phase_name,
            "status":     self.status,
            "duration_s": round(self.duration_s, 3),
            "message":    self.message,
            "detail":     self.detail,
        }

    def __str__(self) -> str:
        icons = {"PASS": _green("✔"), "FAIL": _red("✘"),
                 "SKIP": _yellow("–"), "WARN": _yellow("!")}
        icon  = icons.get(self.status, "?")
        dur   = _dim(f"  [{self.duration_s:.1f}s]")
        base  = f"  {icon}  Phase {self.phase_num:>2}: {self.phase_name:<38s}{dur}"
        if self.message:
            return f"{base}\n        {_dim(self.message)}"
        return base


# ---------------------------------------------------------------------------
# Version configuration
# ---------------------------------------------------------------------------

_VERSION_CONFIG = {
    1: {
        "label":    "Home Maintenance",
        "db_path":  _ROOT / "Version_1" / "03_SQLite_Database" / "fixfinder_v1.db",
        "csv_dir":  _ROOT / "Version_1" / "04_CSV",
        "json_dir": _ROOT / "Version_1" / "05_JSON",
        "emb_path": _ROOT / "Version_1" / "06_Embeddings" / "embeddings.json",
        "faiss_dir":_ROOT / "Version_1" / "12_FAISS",
        "val_dir":  _ROOT / "Version_1" / "13_Validation",
    },
    2: {
        "label":    "Electronics",
        "db_path":  _ROOT / "Version_2" / "03_SQLite_Database" / "fixfinder_v2.db",
        "csv_dir":  _ROOT / "Version_2" / "04_CSV",
        "json_dir": _ROOT / "Version_2" / "05_JSON",
        "emb_path": _ROOT / "Version_2" / "06_Embeddings" / "embeddings.json",
        "faiss_dir":_ROOT / "Version_2" / "12_FAISS",
        "val_dir":  _ROOT / "Version_2" / "13_Validation",
    },
    3: {
        "label":    "Industrial / Automotive",
        "db_path":  _ROOT / "Version_3" / "03_SQLite_Database" / "fixfinder_v3.db",
        "csv_dir":  _ROOT / "Version_3" / "04_CSV",
        "json_dir": _ROOT / "Version_3" / "05_JSON",
        "emb_path": _ROOT / "Version_3" / "06_Embeddings" / "embeddings.json",
        "faiss_dir":_ROOT / "Version_3" / "12_FAISS",
        "val_dir":  _ROOT / "Version_3" / "13_Validation",
    },
}

# ---------------------------------------------------------------------------
# Helper: run a subprocess with timing and captured output
# ---------------------------------------------------------------------------

def _run(
    cmd:     list[str],
    label:   str,
    dry_run: bool = False,
    cwd:     Optional[Path] = None,
) -> tuple[bool, float, str]:
    """
    Run a command as a subprocess.

    Returns (success, elapsed_seconds, combined_output).
    """
    cwd = cwd or _ROOT
    if dry_run:
        log.info("[DRY-RUN] would run: %s", " ".join(cmd))
        return True, 0.0, "[dry-run]"

    log.info("Running: %s", " ".join(cmd))
    t0 = time.perf_counter()
    try:
        result = subprocess.run(
            cmd,
            cwd    = str(cwd),
            capture_output = True,
            text   = True,
            timeout= 600,           # 10-minute hard cap per phase
        )
        elapsed = time.perf_counter() - t0
        output  = (result.stdout + result.stderr).strip()
        if result.returncode != 0:
            log.warning("  exit=%d  stderr: %s",
                        result.returncode, result.stderr[:300])
            return False, elapsed, output
        return True, elapsed, output
    except subprocess.TimeoutExpired:
        return False, time.perf_counter() - t0, "TIMEOUT after 600s"
    except Exception as exc:
        return False, time.perf_counter() - t0, str(exc)


def _python(*args: str) -> list[str]:
    """Return a subprocess command using the current Python interpreter."""
    return [sys.executable, *args]


# ===========================================================================
# ValidationSuite import (used inline for Phase 11)
# ===========================================================================

def _run_validation_inline(version: int) -> tuple[bool, str]:
    """
    Run the ValidationSuite for one version in-process and return
    (all_passed, summary_string).
    """
    try:
        from scripts.validation_suite import ValidationSuite  # type: ignore
    except ImportError:
        try:
            sys.path.insert(0, str(_SCRIPT_DIR))
            from validation_suite import ValidationSuite      # type: ignore
        except ImportError as exc:
            return False, f"Could not import ValidationSuite: {exc}"

    try:
        suite  = ValidationSuite(version=version)
        report = suite.run_all_tests()
        suite.generate_report(save=True)
        suite.close()
        s = report["summary"]
        ok  = report["overall_status"] == "PASS"
        msg = (f"{s['passed']}/{s['total']} tests passed "
               f"({s['pass_rate_pct']}%) — {report['overall_status']}")
        return ok, msg
    except Exception as exc:
        return False, str(exc)

# ===========================================================================
# build_version  — per-version phase runner
# ===========================================================================

def build_version(
    version:    int,
    skip_tests: bool = False,
    force:      bool = False,
    dry_run:    bool = False,
) -> list[PhaseResult]:
    """
    Run all 11 build phases for one version.

    Parameters
    ----------
    version    : int   1 / 2 / 3
    skip_tests : bool  Skip phases 8-10 (unit tests)
    force      : bool  Re-run even if output artefacts already exist
    dry_run    : bool  Log commands without executing them

    Returns
    -------
    List of PhaseResult objects, one per phase.
    """
    cfg     = _VERSION_CONFIG[version]
    label   = cfg["label"]
    results: list[PhaseResult] = []

    def _phase(num: int, name: str) -> None:
        log.info("-" * 60)
        log.info("Phase %d - %s  (v%d: %s)", num, name, version, label)

    # ------------------------------------------------------------------
    # Phase 1 — Master Taxonomy (always skipped)
    # ------------------------------------------------------------------
    _phase(1, "Master Taxonomy")
    results.append(PhaseResult(
        1, "Master Taxonomy", "SKIP", 0.0,
        "Manually authored — skipped",
    ))

    # ------------------------------------------------------------------
    # Phase 2 — Database Schema
    # ------------------------------------------------------------------
    _phase(2, "Database Schema")
    t0 = time.perf_counter()
    db = cfg["db_path"]
    if dry_run:
        results.append(PhaseResult(2, "Database Schema", "SKIP",
                                   0.0, "[dry-run]"))
    elif db.exists():
        # Verify required tables present
        try:
            conn = sqlite3.connect(str(db))
            cur  = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
            )
            n_tables = cur.fetchone()[0]
            conn.close()
            results.append(PhaseResult(
                2, "Database Schema", "PASS",
                time.perf_counter() - t0,
                f"{db.name} verified — {n_tables} tables",
            ))
        except Exception as exc:
            results.append(PhaseResult(
                2, "Database Schema", "FAIL",
                time.perf_counter() - t0, str(exc)))
    else:
        results.append(PhaseResult(
            2, "Database Schema", "FAIL",
            time.perf_counter() - t0,
            f"Database not found: {db}",
            "Run the database initialisation script first.",
        ))

    # ------------------------------------------------------------------
    # Phase 3 — SQLite Database
    # ------------------------------------------------------------------
    _phase(3, "SQLite Database")
    t0 = time.perf_counter()
    if dry_run:
        results.append(PhaseResult(3, "SQLite Database", "SKIP", 0.0, "[dry-run]"))
    elif db.exists():
        try:
            conn = sqlite3.connect(str(db))
            counts = {}
            for tbl in ("systems", "symptoms", "repair_procedures", "parts_inventory"):
                n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                counts[tbl] = n
            conn.close()
            summary = ", ".join(f"{t}={n}" for t, n in counts.items())
            all_ok  = all(n > 0 for n in counts.values())
            results.append(PhaseResult(
                3, "SQLite Database",
                "PASS" if all_ok else "WARN",
                time.perf_counter() - t0,
                summary,
            ))
        except Exception as exc:
            results.append(PhaseResult(
                3, "SQLite Database", "FAIL",
                time.perf_counter() - t0, str(exc)))
    else:
        results.append(PhaseResult(
            3, "SQLite Database", "FAIL",
            time.perf_counter() - t0,
            f"DB file missing: {db}",
        ))

    # ------------------------------------------------------------------
    # Phase 4 — CSV Generation
    # ------------------------------------------------------------------
    _phase(4, "CSV Generation")
    csv_dir  = cfg["csv_dir"]
    csv_ok   = csv_dir.exists() and len(list(csv_dir.glob("*.csv"))) >= 3
    if csv_ok and not force:
        n = len(list(csv_dir.glob("*.csv")))
        results.append(PhaseResult(
            4, "CSV Generation", "SKIP", 0.0,
            f"{n} CSV files already exist (use --force to rebuild)",
        ))
    else:
        ok, elapsed, out = _run(
            _python("generate_csvs.py"), "generate_csvs", dry_run=dry_run)
        n_after = len(list(csv_dir.glob("*.csv"))) if csv_dir.exists() else 0
        results.append(PhaseResult(
            4, "CSV Generation",
            "PASS" if ok else "FAIL",
            elapsed,
            f"{n_after} CSV files generated" if ok else out[:200],
        ))

    # ------------------------------------------------------------------
    # Phase 5 — JSON Generation
    # ------------------------------------------------------------------
    _phase(5, "JSON Generation")
    json_dir  = cfg["json_dir"]
    json_ok   = json_dir.exists() and len(list(json_dir.glob("*.json"))) >= 2
    if json_ok and not force:
        n = len(list(json_dir.glob("*.json")))
        results.append(PhaseResult(
            5, "JSON Generation", "SKIP", 0.0,
            f"{n} JSON files already exist (use --force to rebuild)",
        ))
    else:
        ok, elapsed, out = _run(
            _python("generate_jsons.py"), "generate_jsons", dry_run=dry_run)
        n_after = len(list(json_dir.glob("*.json"))) if json_dir.exists() else 0
        results.append(PhaseResult(
            5, "JSON Generation",
            "PASS" if ok else "FAIL",
            elapsed,
            f"{n_after} JSON files generated" if ok else out[:200],
        ))

    # ------------------------------------------------------------------
    # Phase 6 — Embedding Generation
    # ------------------------------------------------------------------
    _phase(6, "Embedding Generation")
    emb_path = cfg["emb_path"]
    if emb_path.exists() and not force:
        try:
            with open(emb_path) as f:
                d = json.load(f)
            n = d.get("total_embeddings", 0)
            results.append(PhaseResult(
                6, "Embedding Generation", "SKIP", 0.0,
                f"embeddings.json exists ({n} embeddings — use --force to rebuild)",
            ))
        except Exception:
            pass
    else:
        ok, elapsed, out = _run(
            _python("generate_embeddings.py"), "generate_embeddings", dry_run=dry_run)
        if ok and emb_path.exists():
            with open(emb_path) as f:
                d = json.load(f)
            n = d.get("total_embeddings", 0)
            msg = f"{n} embeddings generated, dim={d.get('dimension')}"
        else:
            msg = out[:200] if not ok else "done"
        results.append(PhaseResult(
            6, "Embedding Generation",
            "PASS" if ok else "FAIL", elapsed, msg,
        ))

    # ------------------------------------------------------------------
    # Phase 7 — FAISS Index
    # ------------------------------------------------------------------
    _phase(7, "FAISS Index")
    faiss_dir  = cfg["faiss_dir"]
    faiss_ok   = (faiss_dir / "index.faiss").exists() and \
                 (faiss_dir / "metadata.json").exists()
    if faiss_ok and not force:
        try:
            with open(faiss_dir / "metadata.json") as f:
                m = json.load(f)
            results.append(PhaseResult(
                7, "FAISS Index", "SKIP", 0.0,
                f"index.faiss exists ({m.get('total_entries')} vectors, "
                f"dim={m.get('dimension')} — use --force to rebuild)",
            ))
        except Exception:
            pass
    else:
        ok, elapsed, out = _run(
            _python("build_faiss_indices.py"), "build_faiss", dry_run=dry_run)
        if ok and (faiss_dir / "metadata.json").exists():
            with open(faiss_dir / "metadata.json") as f:
                m = json.load(f)
            msg = (f"IndexFlatIP built: {m.get('total_entries')} vectors, "
                   f"dim={m.get('dimension')}")
        else:
            msg = out[:200] if not ok else "done"
        results.append(PhaseResult(
            7, "FAISS Index",
            "PASS" if ok else "FAIL", elapsed, msg,
        ))

    # ------------------------------------------------------------------
    # Phase 8 — AI Retrieval Engine tests
    # ------------------------------------------------------------------
    _phase(8, "AI Retrieval Engine tests")
    if skip_tests:
        results.append(PhaseResult(8, "AI Retrieval Engine tests",
                                   "SKIP", 0.0, "--skip-tests"))
    elif dry_run:
        results.append(PhaseResult(8, "AI Retrieval Engine tests",
                                   "SKIP", 0.0, "[dry-run]"))
    else:
        ok, elapsed, out = _run(
            _python("tests/test_retrieval.py", "--tests-only"),
            "test_retrieval", dry_run=False)
        msg = _extract_result_line(out) or (out[-200:] if not ok else "all passed")
        results.append(PhaseResult(
            8, "AI Retrieval Engine tests",
            "PASS" if ok else "FAIL", elapsed, msg,
        ))

    # ------------------------------------------------------------------
    # Phase 9 — AI Diagnostic Engine tests
    # ------------------------------------------------------------------
    _phase(9, "AI Diagnostic Engine tests")
    if skip_tests:
        results.append(PhaseResult(9, "AI Diagnostic Engine tests",
                                   "SKIP", 0.0, "--skip-tests"))
    elif dry_run:
        results.append(PhaseResult(9, "AI Diagnostic Engine tests",
                                   "SKIP", 0.0, "[dry-run]"))
    else:
        ok, elapsed, out = _run(
            _python("tests/test_diagnostic.py", "--tests-only"),
            "test_diagnostic", dry_run=False)
        msg = _extract_result_line(out) or (out[-200:] if not ok else "all passed")
        results.append(PhaseResult(
            9, "AI Diagnostic Engine tests",
            "PASS" if ok else "FAIL", elapsed, msg,
        ))

    # ------------------------------------------------------------------
    # Phase 10 — AI Repair Reasoning Engine tests
    # ------------------------------------------------------------------
    _phase(10, "AI Repair Reasoning Engine tests")
    if skip_tests:
        results.append(PhaseResult(10, "AI Repair Reasoning Engine tests",
                                   "SKIP", 0.0, "--skip-tests"))
    elif dry_run:
        results.append(PhaseResult(10, "AI Repair Reasoning Engine tests",
                                   "SKIP", 0.0, "[dry-run]"))
    else:
        ok, elapsed, out = _run(
            _python("tests/test_repair_reasoning.py", "--tests-only"),
            "test_repair", dry_run=False)
        msg = _extract_result_line(out) or (out[-200:] if not ok else "all passed")
        results.append(PhaseResult(
            10, "AI Repair Reasoning Engine tests",
            "PASS" if ok else "FAIL", elapsed, msg,
        ))

    # ------------------------------------------------------------------
    # Phase 11 — Validation Suite
    # ------------------------------------------------------------------
    _phase(11, "Validation Suite")
    t0 = time.perf_counter()
    if dry_run:
        results.append(PhaseResult(11, "Validation Suite", "SKIP", 0.0, "[dry-run]"))
    else:
        ok, msg = _run_validation_inline(version)
        results.append(PhaseResult(
            11, "Validation Suite",
            "PASS" if ok else "FAIL",
            time.perf_counter() - t0,
            msg,
        ))

    return results


def _extract_result_line(output: str) -> str:
    """Pull the 'Results: N/M passed' summary line out of test output."""
    import re
    m = re.search(r"Results:\s*\d+/\d+ passed", output)
    return m.group(0) if m else ""

# ===========================================================================
# build_all  — iterate over all requested versions
# ===========================================================================

def build_all(
    versions:   list[int],
    skip_tests: bool = False,
    force:      bool = False,
    dry_run:    bool = False,
) -> dict[int, list[PhaseResult]]:
    """
    Run build_version() for every requested version.

    Returns
    -------
    dict mapping version int → list[PhaseResult]
    """
    all_results: dict[int, list[PhaseResult]] = {}

    for v in versions:
        cfg = _VERSION_CONFIG[v]
        print()
        print(_bold(_cyan(f"{'='*64}")))
        print(_bold(_cyan(f"  VERSION {v} — {cfg['label']}")))
        print(_bold(_cyan(f"{'='*64}")))

        phase_results = build_version(
            v,
            skip_tests = skip_tests,
            force      = force,
            dry_run    = dry_run,
        )
        all_results[v] = phase_results

        # Print per-phase summary as we go
        for pr in phase_results:
            print(str(pr))

    return all_results


# ===========================================================================
# status_report  — final aggregated summary
# ===========================================================================

def status_report(
    all_results:  dict[int, list[PhaseResult]],
    save:         bool = True,
) -> dict:
    """
    Generate and optionally save the master build report.

    Parameters
    ----------
    all_results : dict[int, list[PhaseResult]]
    save        : bool  Write to scripts/build_report.json

    Returns
    -------
    Report dict
    """
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    version_summaries: list[dict] = []
    grand_phases = grand_pass = grand_fail = grand_skip = 0

    for v, phases in all_results.items():
        cfg       = _VERSION_CONFIG[v]
        n_pass    = sum(1 for p in phases if p.status == "PASS")
        n_fail    = sum(1 for p in phases if p.status == "FAIL")
        n_skip    = sum(1 for p in phases if p.status in ("SKIP", "WARN"))
        total_dur = sum(p.duration_s for p in phases)
        overall   = "PASS" if n_fail == 0 else "FAIL"

        grand_phases += len(phases)
        grand_pass   += n_pass
        grand_fail   += n_fail
        grand_skip   += n_skip

        version_summaries.append({
            "version":        v,
            "version_label":  cfg["label"],
            "overall_status": overall,
            "phases_run":     len(phases),
            "passed":         n_pass,
            "failed":         n_fail,
            "skipped":        n_skip,
            "total_duration_s": round(total_dur, 2),
            "phases": [p.to_dict() for p in phases],
        })

    grand_status = "PASS" if grand_fail == 0 else "FAIL"
    grand_dur    = sum(
        p.duration_s
        for phases in all_results.values()
        for p in phases
    )

    report: dict = {
        "generated_at":   generated_at,
        "overall_status": grand_status,
        "summary": {
            "versions_built":  len(all_results),
            "total_phases":    grand_phases,
            "passed":          grand_pass,
            "failed":          grand_fail,
            "skipped":         grand_skip,
            "total_duration_s": round(grand_dur, 2),
        },
        "versions": version_summaries,
    }

    # Save
    if save:
        report_path = _SCRIPT_DIR / "build_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        log.info("Build report saved: %s", report_path)

    return report


def print_summary(report: dict) -> None:
    """Print the final coloured build summary table to stdout."""
    s = report["summary"]

    print()
    print(_bold("=" * 64))
    print(_bold("  FIXFINDER MASTER BUILD — FINAL SUMMARY"))
    print(_bold("=" * 64))

    status_str = (_green("✔  ALL PASSED") if report["overall_status"] == "PASS"
                  else _red("✘  BUILD FAILED"))
    print(f"  Overall: {status_str}")
    print(f"  Versions built : {s['versions_built']}")
    print(f"  Total phases   : {s['total_phases']}")
    print(f"  Passed         : {_green(str(s['passed']))}")
    print(f"  Failed         : {_red(str(s['failed'])) if s['failed'] else _green('0')}")
    print(f"  Skipped        : {_yellow(str(s['skipped']))}")
    print(f"  Total time     : {s['total_duration_s']:.1f}s")
    print(f"  Generated at   : {report['generated_at']}")
    print()

    # Per-version breakdown
    col_w = 40
    print(f"  {'Version':<12}  {'Status':<8}  {'Phases':>6}  "
          f"{'Pass':>5}  {'Fail':>5}  {'Skip':>5}  {'Time':>7}")
    print("  " + "-" * 62)

    for vs in report["versions"]:
        st_str = _green("PASS") if vs["overall_status"] == "PASS" else _red("FAIL")
        label  = f"v{vs['version']} {vs['version_label']}"
        print(
            f"  {label:<22}  {st_str:<8}  "
            f"{vs['phases_run']:>6}  "
            f"{_green(str(vs['passed'])):>5}  "
            f"{(_red(str(vs['failed'])) if vs['failed'] else '0'):>5}  "
            f"{vs['skipped']:>5}  "
            f"{vs['total_duration_s']:>6.1f}s"
        )

        # Show any failed phases indented
        for ph in vs["phases"]:
            if ph["status"] == "FAIL":
                print(f"       {_red('✘')} Phase {ph['phase']:>2}: "
                      f"{ph['name']}  — {ph['message'][:60]}")

    print()
    print("  Build report: scripts/build_report.json")
    print(_bold("=" * 64))
    print()

# ===========================================================================
# Prerequisite checks
# ===========================================================================

def check_prerequisites() -> bool:
    """
    Verify Python version and required packages are installed before building.
    Returns True if all checks pass.
    """
    print(_bold("\n  Prerequisite checks"))
    print("  " + "-" * 40)

    ok = True

    # Python version
    maj, min_ = sys.version_info[:2]
    py_ok = (maj, min_) >= (3, 10)
    _print_check(f"Python >= 3.10  (found {maj}.{min_})", py_ok)
    if not py_ok:
        ok = False

    # Required packages
    required_pkgs = {
        "faiss":   "faiss",
        "numpy":   "numpy",
        "pytest":  "pytest",
        "fastapi": "fastapi",
        "pydantic":"pydantic",
    }
    for import_name, pkg_label in required_pkgs.items():
        try:
            mod = __import__(import_name)
            ver = getattr(mod, "__version__", "?")
            _print_check(f"{pkg_label}  ({ver})", True)
        except ImportError:
            _print_check(f"{pkg_label}  — NOT INSTALLED", False)
            ok = False

    # Required source scripts
    required_scripts = [
        _ROOT / "generate_csvs.py",
        _ROOT / "generate_jsons.py",
        _ROOT / "generate_embeddings.py",
        _ROOT / "build_faiss_indices.py",
        _ROOT / "tests" / "test_retrieval.py",
        _ROOT / "tests" / "test_diagnostic.py",
        _ROOT / "tests" / "test_repair_reasoning.py",
        _SCRIPT_DIR / "validation_suite.py",
    ]
    for path in required_scripts:
        exists = path.exists()
        _print_check(f"{path.name}", exists)
        if not exists:
            ok = False

    print()
    return ok


def _print_check(label: str, passed: bool) -> None:
    icon = _green("✔") if passed else _red("✘")
    print(f"    {icon}  {label}")


# ===========================================================================
# Ensure directories exist for all versions
# ===========================================================================

def ensure_directories() -> None:
    """Create all required output directories across all three versions."""
    dirs = []
    for v in (1, 2, 3):
        cfg = _VERSION_CONFIG[v]
        dirs.extend([
            cfg["csv_dir"],
            cfg["json_dir"],
            cfg["emb_path"].parent,
            cfg["faiss_dir"],
            cfg["val_dir"],
        ])
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    log.info("Output directories verified.")


# ===========================================================================
# main
# ===========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="FixFinder Master Build Script",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--version", type=int, choices=[1, 2, 3],
        help="Build a single version (default: all three)",
    )
    parser.add_argument(
        "--skip-tests", action="store_true",
        help="Skip unit test phases (8, 9, 10)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-run all phases even if output artefacts already exist",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would run without executing any phase",
    )
    parser.add_argument(
        "--no-save", action="store_true",
        help="Do not write build_report.json",
    )
    parser.add_argument(
        "--summary-only", action="store_true",
        help="Only print the final summary of the last saved build report",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Set logging level to DEBUG",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # ── summary-only mode ────────────────────────────────────────────────────
    if args.summary_only:
        report_path = _SCRIPT_DIR / "build_report.json"
        if not report_path.exists():
            print(_red("No build_report.json found. Run the build first."))
            sys.exit(1)
        with open(report_path) as f:
            rpt = json.load(f)
        print_summary(rpt)
        sys.exit(0 if rpt["overall_status"] == "PASS" else 1)

    # ── header ───────────────────────────────────────────────────────────────
    print()
    print(_bold(_cyan("=" * 64)))
    print(_bold(_cyan("  FIXFINDER MASTER BUILD")))
    print(_bold(_cyan("=" * 64)))
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Root   : {_ROOT}")

    if args.dry_run:
        print(_yellow("  [DRY-RUN MODE — no commands will be executed]"))

    # ── prerequisites ────────────────────────────────────────────────────────
    if not check_prerequisites():
        print(_red("  ✘  Prerequisites not met. Aborting build."))
        sys.exit(1)

    # ── directories ──────────────────────────────────────────────────────────
    if not args.dry_run:
        ensure_directories()

    # ── run ──────────────────────────────────────────────────────────────────
    versions     = [args.version] if args.version else [1, 2, 3]
    all_results  = build_all(
        versions    = versions,
        skip_tests  = args.skip_tests,
        force       = args.force,
        dry_run     = args.dry_run,
    )

    # ── report ───────────────────────────────────────────────────────────────
    report = status_report(all_results, save=not args.no_save)
    print_summary(report)

    sys.exit(0 if report["overall_status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
