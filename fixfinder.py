"""
fixfinder.py
=============
FixFinder complete integration script.

Wires together all three AI engines (Retrieval, Diagnostic, Repair Reasoning)
across all three versioned knowledge bases into a single unified interface.

CLI usage
---------
  python fixfinder.py --search  "roof leaking near chimney"
  python fixfinder.py --diagnose "electrical outlet dead no power"
  python fixfinder.py --repair  "PRB-ROF-002"
  python fixfinder.py --info    "ROF-001" --version 1
  python fixfinder.py --stats   1
  python fixfinder.py --list-versions
  python fixfinder.py --demo

Programmatic usage
------------------
  from fixfinder import FixFinderSystem

  with FixFinderSystem() as ff:
      results = ff.search_all("battery drains fast")
      plan    = ff.repair_all("PRB-ROF-002")
      stats   = ff.get_version_stats(1)
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Workspace root (so engines import cleanly wherever this file lives)
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from ai_engine.retrieval_engine        import AIRetrievalEngine        # noqa: E402
from ai_engine.diagnostic_engine       import AIDiagnosticEngine       # noqa: E402
from ai_engine.repair_reasoning_engine import AIRepairReasoningEngine  # noqa: E402

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

_USE_COLOUR = sys.stdout.isatty()

def _c(s: str, code: str) -> str:
    return f"\033[{code}m{s}\033[0m" if _USE_COLOUR else s

def _green(s: str)  -> str: return _c(s, "32")
def _red(s: str)    -> str: return _c(s, "31")
def _yellow(s: str) -> str: return _c(s, "33")
def _cyan(s: str)   -> str: return _c(s, "36")
def _bold(s: str)   -> str: return _c(s, "1")
def _dim(s: str)    -> str: return _c(s, "2")

# ---------------------------------------------------------------------------
# Version metadata
# ---------------------------------------------------------------------------

VERSION_META: dict[int, dict] = {
    1: {
        "version_str":  "1.0",
        "label":        "Home Maintenance",
        "emoji":        "🏠",
        "description":  "Roofing, plumbing, electrical, HVAC, and home systems",
        "db_path":      os.path.join(_HERE, "Version_1", "03_SQLite_Database", "fixfinder_v1.db"),
        "embed_path":   os.path.join(_HERE, "Version_1", "06_Embeddings", "embeddings.json"),
        "faiss_dir":    os.path.join(_HERE, "Version_1", "12_FAISS"),
        "json_dir":     os.path.join(_HERE, "Version_1", "05_JSON"),
        "val_report":   os.path.join(_HERE, "Version_1", "13_Validation", "validation_report.json"),
    },
    2: {
        "version_str":  "2.0",
        "label":        "Electronics",
        "emoji":        "📱",
        "description":  "Smartphones, laptops, TVs, gaming consoles, and electronics",
        "db_path":      os.path.join(_HERE, "Version_2", "03_SQLite_Database", "fixfinder_v2.db"),
        "embed_path":   os.path.join(_HERE, "Version_2", "06_Embeddings", "embeddings.json"),
        "faiss_dir":    os.path.join(_HERE, "Version_2", "12_FAISS"),
        "json_dir":     os.path.join(_HERE, "Version_2", "05_JSON"),
        "val_report":   os.path.join(_HERE, "Version_2", "13_Validation", "validation_report.json"),
    },
    3: {
        "version_str":  "3.0",
        "label":        "Industrial / Automotive",
        "emoji":        "🔧",
        "description":  "Cars, trucks, heavy equipment, generators, and industrial systems",
        "db_path":      os.path.join(_HERE, "Version_3", "03_SQLite_Database", "fixfinder_v3.db"),
        "embed_path":   os.path.join(_HERE, "Version_3", "06_Embeddings", "embeddings.json"),
        "faiss_dir":    os.path.join(_HERE, "Version_3", "12_FAISS"),
        "json_dir":     os.path.join(_HERE, "Version_3", "05_JSON"),
        "val_report":   os.path.join(_HERE, "Version_3", "13_Validation", "validation_report.json"),
    },
}


# ===========================================================================
# FixFinderSystem
# ===========================================================================

class FixFinderSystem:
    """
    Unified interface to all three FixFinder AI engines.

    Handles engine lifecycle, cross-version queries, and structured output.

    Usage
    -----
        # As a context manager (recommended — ensures clean shutdown)
        with FixFinderSystem() as ff:
            results = ff.search_all("roof leaking after rain")

        # Explicit lifecycle
        ff = FixFinderSystem()
        ff.load_all_versions()
        results = ff.search_all("battery drains fast")
        ff.close()
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, versions: list[str] | None = None) -> None:
        """
        Parameters
        ----------
        versions : list of version strings, e.g. ['1.0', '2.0', '3.0'].
                   Defaults to all three versions.
        """
        requested = versions or ["1.0", "2.0", "3.0"]
        # Map "1.0" → 1, "2.0" → 2, "3.0" → 3
        self._version_ints: list[int] = []
        for vs in requested:
            v = int(float(vs))
            if v not in VERSION_META:
                raise ValueError(f"Unknown version {vs!r}. Valid: '1.0', '2.0', '3.0'")
            self._version_ints.append(v)

        # Engine pools — populated by load_all_versions()
        self._retrieval: dict[int, AIRetrievalEngine]       = {}
        self._diagnostic: dict[int, AIDiagnosticEngine]     = {}
        self._repair: dict[int, AIRepairReasoningEngine]     = {}
        self._load_errors: dict[str, str]                   = {}
        self._loaded = False

        # Pre-load eagerly on construction
        self.load_all_versions()

    # ------------------------------------------------------------------
    # load_all_versions
    # ------------------------------------------------------------------

    def load_all_versions(self) -> dict[str, Any]:
        """
        Load all three AI engines for every requested version.

        Returns
        -------
        dict  {version_int: {"retrieval": bool, "diagnostic": bool, "repair": bool}}
        """
        status: dict[int, dict] = {}

        for v in self._version_ints:
            vstatus: dict[str, bool] = {}
            meta = VERSION_META[v]

            for EngClass, pool, key in (
                (AIRetrievalEngine,       self._retrieval,  "retrieval"),
                (AIDiagnosticEngine,      self._diagnostic, "diagnostic"),
                (AIRepairReasoningEngine, self._repair,     "repair"),
            ):
                err_key = f"v{v}_{key}"
                try:
                    if v not in pool:
                        pool[v] = EngClass(version=v)
                    vstatus[key] = True
                except Exception as exc:
                    self._load_errors[err_key] = str(exc)
                    vstatus[key] = False

            status[v] = vstatus

        self._loaded = True
        return status

    # ------------------------------------------------------------------
    # search_all
    # ------------------------------------------------------------------

    def search_all(
        self,
        query:       str,
        top_k:       int = 5,
        entity_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Semantic FAISS search across all loaded versions.

        Parameters
        ----------
        query       : Free-text search string.
        top_k       : Results per version (default 5).
        entity_type : Optional filter — "system", "symptom", or "repair".

        Returns
        -------
        dict with keys:
          query, entity_type, versions_searched,
          all_results (merged + re-ranked),
          by_version {version_int: [results]}
        """
        if not query or not query.strip():
            raise ValueError("query must not be empty.")

        by_version: dict[int, list] = {}
        all_results: list[dict]     = []
        errors: list[dict]          = []

        for v in self._version_ints:
            if v not in self._retrieval:
                errors.append({"version": v, "error": "engine not loaded"})
                continue
            try:
                results = self._retrieval[v].search(
                    query_text         = query,
                    top_k              = top_k,
                    entity_type_filter = entity_type,
                )
                for r in results:
                    r["version"]       = v
                    r["version_label"] = VERSION_META[v]["label"]
                by_version[v] = results
                all_results.extend(results)
            except Exception as exc:
                errors.append({"version": v, "error": str(exc)})

        # Re-rank globally
        all_results.sort(key=lambda x: x["score"], reverse=True)
        all_results = all_results[:top_k]
        for i, r in enumerate(all_results):
            r["global_rank"] = i + 1

        return {
            "query":            query,
            "entity_type":      entity_type,
            "top_k":            top_k,
            "versions_searched": self._version_ints,
            "total_results":    len(all_results),
            "all_results":      all_results,
            "by_version":       by_version,
            "errors":           errors or None,
        }

    # ------------------------------------------------------------------
    # diagnose_all
    # ------------------------------------------------------------------

    def diagnose_all(
        self,
        user_input: str,
        top_k:      int = 5,
    ) -> dict[str, Any]:
        """
        Run symptom analysis across all loaded versions.

        For each version: tokenise input, score against symptoms table,
        auto-run tree traversal for the top match if confidence >= 0.15.

        Returns
        -------
        dict with keys:
          user_input, by_version {version_int: {matches, tree_result}},
          best_match (highest-scored match across all versions)
        """
        if not user_input or not user_input.strip():
            raise ValueError("user_input must not be empty.")

        by_version: dict[int, dict] = {}
        best_score  = 0.0
        best_match: Optional[dict] = None

        for v in self._version_ints:
            if v not in self._diagnostic:
                by_version[v] = {"error": "engine not loaded"}
                continue
            try:
                diag = self._diagnostic[v]
                matches = diag.analyze_symptoms(user_input, top_k=top_k)

                tree_result: Optional[dict] = None
                if matches and matches[0]["score"] >= 0.15:
                    top_code   = matches[0]["symptom_code"]
                    tree_result = diag.run_diagnostic(top_code, user_responses=[])

                by_version[v] = {
                    "version_label": VERSION_META[v]["label"],
                    "total_matches": len(matches),
                    "matches":       matches,
                    "tree_result":   tree_result,
                }

                if matches and matches[0]["score"] > best_score:
                    best_score = matches[0]["score"]
                    best_match = {**matches[0], "version": v,
                                  "version_label": VERSION_META[v]["label"]}

            except Exception as exc:
                by_version[v] = {"error": str(exc)}

        return {
            "user_input": user_input,
            "by_version": by_version,
            "best_match": best_match,
        }

    # ------------------------------------------------------------------
    # repair_all
    # ------------------------------------------------------------------

    def repair_all(
        self,
        symptom_code:      str,
        diagnostic_result: Optional[dict] = None,
        top_k:             int = 3,
    ) -> dict[str, Any]:
        """
        Generate a repair plan for a symptom across all relevant versions.

        The version is inferred from the symptom_code prefix (ROF→v1,
        PHN→v2, CAR→v3).  Falls back to searching all versions.

        Returns
        -------
        dict with keys:
          symptom_code, best_plan (highest-confidence plan),
          by_version {version_int: plan_dict}
        """
        if not symptom_code or not symptom_code.strip():
            raise ValueError("symptom_code must not be empty.")

        # Infer the most relevant version from the code prefix
        inferred = self._infer_version(symptom_code)
        targets  = [inferred] if inferred else self._version_ints

        by_version: dict[int, dict] = {}
        best_plan: Optional[dict]   = None
        best_score = 0.0

        for v in targets:
            if v not in self._repair:
                by_version[v] = {"error": "engine not loaded"}
                continue
            try:
                plan = self._repair[v].generate_repair_plan(
                    symptom_code      = symptom_code,
                    diagnostic_result = diagnostic_result,
                    top_k             = top_k,
                )
                plan["version"]       = v
                plan["version_label"] = VERSION_META[v]["label"]
                by_version[v]         = plan

                # Score the plan by primary repair relevance
                primary     = plan.get("primary_repair") or {}
                plan_score  = primary.get("relevance_score", 0.0) or 0.0
                if plan_score > best_score:
                    best_score = plan_score
                    best_plan  = plan

            except Exception as exc:
                by_version[v] = {"error": str(exc)}

        # If no primary repair anywhere, pick the first non-error plan
        if best_plan is None:
            for v, p in by_version.items():
                if "error" not in p:
                    best_plan = p
                    break

        return {
            "symptom_code":     symptom_code,
            "inferred_version": inferred,
            "by_version":       by_version,
            "best_plan":        best_plan,
        }

    # ------------------------------------------------------------------
    # get_system_info
    # ------------------------------------------------------------------

    def get_system_info(
        self,
        system_id: str,
        version:   Optional[int] = None,
    ) -> Optional[dict]:
        """
        Fetch system details from SQLite.

        Searches the specified version first; if version is None, tries
        all loaded versions and returns the first match.
        """
        targets = [version] if version else self._version_ints
        for v in targets:
            if v not in self._retrieval:
                continue
            try:
                result = self._retrieval[v].get_system_details(system_id)
                if result:
                    result["_version"]       = v
                    result["_version_label"] = VERSION_META[v]["label"]
                    return result
            except Exception:
                continue
        return None

    # ------------------------------------------------------------------
    # get_symptom_info
    # ------------------------------------------------------------------

    def get_symptom_info(
        self,
        symptom_id: str,
        version:    Optional[int] = None,
    ) -> Optional[dict]:
        """
        Fetch symptom details from SQLite.
        Tries all versions if version is None.
        """
        targets = [version] if version else self._version_ints
        for v in targets:
            if v not in self._retrieval:
                continue
            try:
                result = self._retrieval[v].get_symptom_details(symptom_id)
                if result:
                    result["_version"]       = v
                    result["_version_label"] = VERSION_META[v]["label"]
                    return result
            except Exception:
                continue
        return None

    # ------------------------------------------------------------------
    # get_repair_info
    # ------------------------------------------------------------------

    def get_repair_info(
        self,
        repair_id: str,
        version:   Optional[int] = None,
    ) -> Optional[dict]:
        """
        Fetch repair procedure from SQLite.
        Tries all versions if version is None.
        """
        targets = [version] if version else self._version_ints
        for v in targets:
            if v not in self._retrieval:
                continue
            try:
                result = self._retrieval[v].get_repair_procedure(repair_id)
                if result:
                    result["_version"]       = v
                    result["_version_label"] = VERSION_META[v]["label"]
                    return result
            except Exception:
                continue
        return None

    # ------------------------------------------------------------------
    # get_version_stats
    # ------------------------------------------------------------------

    def get_version_stats(self, version: int) -> dict:
        """
        Return comprehensive statistics for a single version.

        Includes SQLite table counts, embedding info, FAISS index info,
        JSON artefact counts, and latest validation report summary.

        Parameters
        ----------
        version : int  1, 2, or 3
        """
        if version not in VERSION_META:
            raise ValueError(f"version must be 1, 2, or 3 — got {version!r}")

        meta  = VERSION_META[version]
        stats: dict[str, Any] = {
            "version":       version,
            "version_str":   meta["version_str"],
            "label":         meta["label"],
            "description":   meta["description"],
            "engines_loaded": {
                "retrieval":  version in self._retrieval,
                "diagnostic": version in self._diagnostic,
                "repair":     version in self._repair,
            },
        }

        # ── SQLite counts ──────────────────────────────────────────────
        db_path = meta["db_path"]
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            db_stats: dict[str, int] = {}
            for table in ("systems", "symptoms", "repair_procedures",
                          "parts_inventory", "categories", "diagnostic_trees"):
                try:
                    db_stats[table] = conn.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0]
                except Exception:
                    db_stats[table] = -1

            # parts in-stock rate
            try:
                total = db_stats.get("parts_inventory", 0)
                in_stock = conn.execute(
                    "SELECT COUNT(*) FROM parts_inventory WHERE current_stock > 0"
                ).fetchone()[0]
                db_stats["parts_in_stock"] = in_stock
                db_stats["parts_in_stock_pct"] = (
                    round(100 * in_stock / total, 1) if total else 0
                )
            except Exception:
                pass

            # symptom severity breakdown
            try:
                sev_rows = conn.execute(
                    "SELECT severity, COUNT(*) c FROM symptoms "
                    "GROUP BY severity ORDER BY c DESC"
                ).fetchall()
                db_stats["symptom_severity_breakdown"] = {
                    r["severity"]: r["c"] for r in sev_rows
                }
            except Exception:
                pass

            conn.close()
            stats["database"] = {
                "path":   db_path,
                "size_kb": round(os.path.getsize(db_path) / 1024, 1),
                "counts": db_stats,
            }
        else:
            stats["database"] = {"error": f"not found: {db_path}"}

        # ── Embeddings ─────────────────────────────────────────────────
        ep = meta["embed_path"]
        if os.path.exists(ep):
            with open(ep) as f:
                emb = json.load(f)
            by_type: dict[str, int] = {}
            for e in emb.get("embeddings", []):
                t = e.get("entity_type", "unknown")
                by_type[t] = by_type.get(t, 0) + 1
            stats["embeddings"] = {
                "path":             ep,
                "total":            emb.get("total_embeddings", 0),
                "dimension":        emb.get("dimension", 0),
                "by_entity_type":   by_type,
            }
        else:
            stats["embeddings"] = {"error": "not found"}

        # ── FAISS ──────────────────────────────────────────────────────
        fm = os.path.join(meta["faiss_dir"], "metadata.json")
        fi = os.path.join(meta["faiss_dir"], "index.faiss")
        if os.path.exists(fm):
            with open(fm) as f:
                fmeta = json.load(f)
            stats["faiss"] = {
                "index_path":    fi,
                "index_size_kb": round(os.path.getsize(fi) / 1024, 1)
                                 if os.path.exists(fi) else None,
                "index_type":    fmeta.get("index_type"),
                "total_entries": fmeta.get("total_entries"),
                "dimension":     fmeta.get("dimension"),
                "categories":    list(fmeta.get("mapping", {}).keys()),
            }
        else:
            stats["faiss"] = {"error": "metadata.json not found"}

        # ── JSON artefacts ─────────────────────────────────────────────
        jd  = meta["json_dir"]
        jstats: dict[str, Any] = {}
        for fn in ("diagnostic_trees.json", "repair_procedures.json"):
            p = os.path.join(jd, fn)
            if os.path.exists(p):
                with open(p) as f:
                    d = json.load(f)
                jstats[fn] = {
                    "count": len(d),
                    "keys":  list(d.keys()),
                }
            else:
                jstats[fn] = {"error": "not found"}
        stats["json_artefacts"] = jstats

        # ── Validation report ──────────────────────────────────────────
        vp = meta["val_report"]
        if os.path.exists(vp):
            with open(vp) as f:
                vr = json.load(f)
            stats["last_validation"] = {
                "generated_at":  vr.get("generated_at"),
                "overall_status": vr.get("overall_status"),
                "summary":       vr.get("summary"),
            }
        else:
            stats["last_validation"] = {"status": "report not found"}

        return stats

    # ------------------------------------------------------------------
    # close / context manager
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release all SQLite connections held by every engine instance."""
        for pool in (self._retrieval, self._diagnostic, self._repair):
            for eng in pool.values():
                try:
                    eng.close()
                except Exception:
                    pass
        self._retrieval.clear()
        self._diagnostic.clear()
        self._repair.clear()

    def __enter__(self) -> "FixFinderSystem":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        loaded = [v for v in self._version_ints if v in self._retrieval]
        return (
            f"FixFinderSystem(versions={self._version_ints}, "
            f"loaded={loaded})"
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    _PREFIX_TO_VERSION: dict[str, int] = {
        # v1 – Home Maintenance
        "ROF": 1, "FND": 1, "PLM": 1, "ELC": 1, "HVC": 1,
        "EXT": 1, "WIN": 1, "GRG": 1, "SMP": 1, "APL": 1,
        # v2 – Electronics
        "PHN": 2, "TAB": 2, "LAP": 2, "DKT": 2, "TV":  2,
        "AUD": 2, "CAM": 2, "NET": 2, "GAM": 2, "WRB": 2,
        # v3 – Industrial / Automotive
        "CAR": 3, "TRK": 3, "MCY": 3, "HVY": 3, "HEQ": 3,
        "GEN": 3, "CMP": 3, "PMP": 3, "MOT": 3, "VAN": 3,
        "SUV": 3, "EV":  3, "SOL": 3,
    }

    def _infer_version(self, entity_id: str) -> Optional[int]:
        """Infer version (1/2/3) from an entity_id prefix."""
        parts = entity_id.upper().split("-")
        for part in parts:
            if part in self._PREFIX_TO_VERSION:
                v = self._PREFIX_TO_VERSION[part]
                if v in self._version_ints:
                    return v
        return None


# ===========================================================================
# Output helpers shared by demo and CLI
# ===========================================================================

def _header(title: str, width: int = 64) -> None:
    print()
    print(_bold(_cyan("=" * width)))
    print(_bold(_cyan(f"  {title}")))
    print(_bold(_cyan("=" * width)))


def _section(title: str) -> None:
    print()
    print(_bold(f"  ── {title}"))


def _print_search_results(result: dict, max_show: int = 5) -> None:
    _section("Search Results")
    print(f"  Query: {_yellow(repr(result['query']))}")
    print(f"  Versions searched: {result['versions_searched']}  |  "
          f"Total results: {result['total_results']}")
    for r in result["all_results"][:max_show]:
        type_colours = {
            "system":  _green,
            "symptom": _yellow,
            "repair":  _cyan,
        }
        col   = type_colours.get(r["entity_type"], str)
        label = f"v{r['version']} {r['version_label']}"
        print(
            f"    {r['global_rank']:>2}.  {col(r['entity_id']):<22s} "
            f"type={r['entity_type']:<8s}  score={r['score']:.4f}  "
            f"{_dim(label)}"
        )


def _print_diagnosis(result: dict, max_matches: int = 3) -> None:
    _section("Diagnostic Results")
    print(f"  Input: {_yellow(repr(result['user_input']))}")
    if result["best_match"]:
        bm = result["best_match"]
        print(
            f"  Best match: {_green(bm['symptom_name'])}  "
            f"({bm['symptom_code']})  "
            f"severity={bm['severity']}  "
            f"score={bm['score']:.4f}  "
            f"{_dim('v' + str(bm['version']) + ' ' + bm['version_label'])}"
        )
    for v, data in result["by_version"].items():
        if "error" in data:
            continue
        label = data.get("version_label", f"v{v}")
        print(f"\n  {_bold(f'Version {v} — {label}')}:")
        for m in data["matches"][:max_matches]:
            print(
                f"    {m['rank']:>2}.  {m['symptom_name']:<40s} "
                f"sev={m['severity']:<10s} score={m['score']:.4f}"
            )
            print(f"          code={m['symptom_code']}  "
                  f"tokens={m['matched_tokens'][:4]}")
        if data.get("tree_result"):
            tr = data["tree_result"]
            action = tr.get("recommended_action", "")
            rcode  = tr.get("repair_code")
            print(f"\n    Tree traversal for {tr.get('symptom_code', '?')}:")
            print(f"      Recommended action: {_green(action[:80])}")
            if rcode:
                print(f"      Repair code: {_cyan(rcode)}")


def _print_repair_plan(result: dict) -> None:
    _section("Repair Plan")
    print(f"  Symptom: {_yellow(result['symptom_code'])}")
    plan = result.get("best_plan")
    if not plan or not plan.get("primary_repair"):
        print(f"  {_yellow('No matching repair found.')}")
        return
    print(f"  {_bold('Summary')}: {_green(plan.get('summary', ''))}")
    print(f"  Difficulty : {plan.get('difficulty', '?')}")
    print(f"  Est. time  : {plan.get('total_estimated_time_minutes', '?')} min")
    print(f"  Parts cost : ${plan.get('total_parts_cost', 0):.2f}")
    print(f"  Urgency    : {plan.get('urgency', '?')}")
    avail = _green("ALL IN STOCK") if plan.get("all_parts_available") \
        else _yellow("SOME PARTS MISSING")
    print(f"  Parts avail: {avail}")
    # Top 3 plan steps
    steps = plan.get("plan_steps", [])
    if steps:
        print(f"\n  {_bold('First steps')}:")
        for s in steps[:5]:
            print(f"    {s}")
        if len(steps) > 5:
            print(f"    {_dim(f'… +{len(steps)-5} more steps')}")
    # Alternatives
    alts = plan.get("alternative_repairs", [])
    if alts:
        alt_strs = [f"{a['id']} ({a['difficulty']})" for a in alts[:3]]
        print(f"\n  {_bold('Alternatives')}: {', '.join(alt_strs)}")


def _print_entity(entity: dict) -> None:
    _section("Entity Details")
    v = entity.get("_version", "?")
    print(f"  Version: {v} — {entity.get('_version_label', '')}")
    # Remove internal keys before printing
    display = {k: v for k, v in entity.items() if not k.startswith("_")}
    for key, val in display.items():
        if isinstance(val, list):
            val = val[:3]
        elif isinstance(val, dict):
            val = {k2: str(v2)[:60] for k2, v2 in list(val.items())[:4]}
        print(f"  {key:<32s}: {val}")


def _print_stats(stats: dict) -> None:
    _section(f"Version {stats['version']} Statistics — {stats['label']}")
    print(f"  Description: {stats['description']}")
    engines = stats.get("engines_loaded", {})
    eng_str = "  ".join(
        f"{k}: {_green('✔') if v else _red('✘')}"
        for k, v in engines.items()
    )
    print(f"  Engines: {eng_str}")

    db = stats.get("database", {})
    if "counts" in db:
        c = db["counts"]
        print(f"\n  {_bold('Database')} ({db.get('size_kb', '?')} KB):")
        for t in ("systems", "symptoms", "repair_procedures",
                  "parts_inventory", "categories", "diagnostic_trees"):
            print(f"    {t:<30s}: {c.get(t, '?')}")
        in_pct = c.get("parts_in_stock_pct", "?")
        print(f"    parts in stock            : {c.get('parts_in_stock', '?')}"
              f"  ({in_pct}%)")
        sev = c.get("symptom_severity_breakdown", {})
        if sev:
            sev_str = "  ".join(f"{k}={v}" for k, v in sev.items())
            print(f"    symptom severity          : {sev_str}")

    emb = stats.get("embeddings", {})
    if "total" in emb:
        print(f"\n  {_bold('Embeddings')}: "
              f"total={emb['total']}, dim={emb['dimension']}")
        for t, n in emb.get("by_entity_type", {}).items():
            print(f"    {t:<12s}: {n}")

    fi = stats.get("faiss", {})
    if "total_entries" in fi:
        print(f"\n  {_bold('FAISS')} ({fi.get('index_size_kb', '?')} KB):")
        print(f"    type={fi['index_type']}, "
              f"entries={fi['total_entries']}, "
              f"dim={fi['dimension']}")
        print(f"    categories: {', '.join(fi.get('categories', [])[:6])}")

    jv = stats.get("last_validation", {})
    if jv.get("overall_status"):
        status_col = _green if jv["overall_status"] == "PASS" else _red
        s = jv.get("summary", {})
        print(f"\n  {_bold('Last Validation')}: "
              f"{status_col(jv['overall_status'])}  "
              f"{s.get('passed', '?')}/{s.get('total', '?')} tests  "
              f"({s.get('pass_rate_pct', '?')}%)  "
              f"{_dim(jv.get('generated_at', ''))}")


# ===========================================================================
# Demo function
# ===========================================================================

DEMO_QUERIES = {
    "search": [
        "roof leaking badly after heavy rain near chimney",
        "iPhone battery drains fast won't charge",
        "check engine light on O2 sensor misfire",
    ],
    "diagnose": [
        ("electrical outlet completely dead no power bathroom", 1),
        ("laptop overheating shuts down during gaming fan loud",  2),
        ("excavator hydraulic arm moving slowly losing pressure",  3),
    ],
    "repair": [
        ("PRB-ROF-002", 1, {"repair_code": "RP-ROF-001", "category": "Roofing"}),
        ("PRB-PHN-001", 2, {"repair_code": "RP-PHN-001", "category": "Phones"}),
        ("PRB-CAR-001", 3, {"repair_code": "RP-CAR-001", "category": "Cars"}),
    ],
}


def demo() -> None:
    """
    Full walkthrough of all FixFinder capabilities across all three versions.
    Loads engines, runs sample queries, and prints structured results.
    """
    _header("FIXFINDER AI ENGINE — FULL DEMO")
    print(f"  {_dim('Started: ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}")

    t_start = time.perf_counter()

    print("\n  Loading all engines …")
    ff = FixFinderSystem()
    print(f"  {_green('✔')} {ff}")

    # ── 1. List versions ─────────────────────────────────────────────────────
    _header("STEP 1 — Version Overview")
    for v in [1, 2, 3]:
        meta = VERSION_META[v]
        stats = ff.get_version_stats(v)
        db    = stats.get("database", {}).get("counts", {})
        print(f"  v{v} {meta['label']}")
        print(f"     systems={db.get('systems','?')}  "
              f"symptoms={db.get('symptoms','?')}  "
              f"repairs={db.get('repair_procedures','?')}  "
              f"parts={db.get('parts_inventory','?')}")

    # ── 2. Search ─────────────────────────────────────────────────────────────
    _header("STEP 2 — Semantic Search")
    for q in DEMO_QUERIES["search"]:
        result = ff.search_all(q, top_k=3)
        _print_search_results(result, max_show=3)

    # ── 3. Diagnose ───────────────────────────────────────────────────────────
    _header("STEP 3 — Symptom Analysis & Diagnosis")
    for user_input, version in DEMO_QUERIES["diagnose"]:
        # Single-version diagnosis for clarity
        single_ff = FixFinderSystem(versions=[str(float(version))])
        result = single_ff.diagnose_all(user_input, top_k=3)
        _print_diagnosis(result, max_matches=3)
        single_ff.close()

    # ── 4. Repair plans ───────────────────────────────────────────────────────
    _header("STEP 4 — Repair Plan Generation")
    for symptom_code, version, diag_result in DEMO_QUERIES["repair"]:
        single_ff = FixFinderSystem(versions=[str(float(version))])
        result = single_ff.repair_all(symptom_code, diagnostic_result=diag_result)
        _print_repair_plan(result)
        single_ff.close()

    # ── 5. Entity lookups ─────────────────────────────────────────────────────
    _header("STEP 5 — Entity Detail Lookups")
    lookups = [
        ("system",  "ROF-001",      1),
        ("symptom", "PRB-PHN-001",  2),
        ("repair",  "rep_car_o2",   3),
    ]
    for etype, eid, v in lookups:
        _section(f"  {etype.capitalize()}: {eid}  (v{v})")
        if etype == "system":
            info = ff.get_system_info(eid, version=v)
        elif etype == "symptom":
            info = ff.get_symptom_info(eid, version=v)
        else:
            info = ff.get_repair_info(eid, version=v)
        if info:
            print(f"    Name    : {info.get('system_name') or info.get('symptom_name') or info.get('repair_name', '?')}")
            print(f"    Version : {info.get('_version_label', '?')}")
        else:
            print(f"    {_yellow('Not found in version')} {v}")

    # ── 6. Version stats ──────────────────────────────────────────────────────
    _header("STEP 6 — Version Statistics")
    for v in [1, 2, 3]:
        _print_stats(ff.get_version_stats(v))

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = round(time.perf_counter() - t_start, 2)
    _header("DEMO COMPLETE")
    print(f"  Total time : {elapsed}s")
    print(f"  Versions   : {ff._version_ints}")
    print()

    ff.close()


# ===========================================================================
# CLI
# ===========================================================================

def _cli_search(args: argparse.Namespace, ff: FixFinderSystem) -> None:
    result = ff.search_all(
        query       = args.search,
        top_k       = args.top_k,
        entity_type = args.entity_type or None,
    )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        _header(f"Search: {args.search}")
        _print_search_results(result, max_show=args.top_k)


def _cli_diagnose(args: argparse.Namespace, ff: FixFinderSystem) -> None:
    result = ff.diagnose_all(args.diagnose, top_k=args.top_k)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        _header(f"Diagnose: {args.diagnose}")
        _print_diagnosis(result, max_matches=args.top_k)


def _cli_repair(args: argparse.Namespace, ff: FixFinderSystem) -> None:
    result = ff.repair_all(args.repair)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        _header(f"Repair Plan: {args.repair}")
        _print_repair_plan(result)


def _cli_info(args: argparse.Namespace, ff: FixFinderSystem) -> None:
    v = args.version or None
    eid = args.info
    # Try all three entity types
    info = (
        ff.get_system_info(eid, version=v) or
        ff.get_symptom_info(eid, version=v) or
        ff.get_repair_info(eid, version=v)
    )
    if args.json:
        print(json.dumps(info, indent=2))
    else:
        _header(f"Entity: {eid}")
        if info:
            _print_entity(info)
        else:
            print(f"  {_red('Not found:')} {eid!r}"
                  + (f" in version {v}" if v else " in any version"))


def _cli_stats(args: argparse.Namespace, ff: FixFinderSystem) -> None:
    v = int(args.stats)
    stats = ff.get_version_stats(v)
    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        _header(f"Stats — Version {v}")
        _print_stats(stats)


def _cli_list_versions(args: argparse.Namespace, ff: FixFinderSystem) -> None:
    _header("Available Versions")
    for v, meta in VERSION_META.items():
        loaded = v in ff._retrieval
        icon   = _green("✔") if loaded else _yellow("○")
        print(f"  {icon}  v{meta['version_str']}  {meta['label']}")
        print(f"       {meta['description']}")
        if args.json:
            continue
        db = meta["db_path"]
        if os.path.exists(db):
            sz = round(os.path.getsize(db) / 1024, 1)
            print(f"       DB: {db}  ({sz} KB)")
    if args.json:
        data = {v: {"version_str": m["version_str"], "label": m["label"],
                    "description": m["description"]}
                for v, m in VERSION_META.items()}
        print(json.dumps(data, indent=2))


# ===========================================================================
# Entry point
# ===========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        prog        = "fixfinder",
        description = "FixFinder AI Engine — unified CLI",
        formatter_class = argparse.RawDescriptionHelpFormatter,
        epilog = """\
Examples:
  python fixfinder.py --search "roof leaking after rain"
  python fixfinder.py --diagnose "outlet dead no power"
  python fixfinder.py --repair "PRB-ROF-002"
  python fixfinder.py --info "ROF-001" --version 1
  python fixfinder.py --stats 1
  python fixfinder.py --list-versions
  python fixfinder.py --demo
  python fixfinder.py --search "battery" --json
""",
    )

    # ── Actions (mutually exclusive) ─────────────────────────────────────────
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--search",        metavar="QUERY",
                        help="Semantic search across all versions")
    action.add_argument("--diagnose",      metavar="TEXT",
                        help="Symptom analysis + guided diagnosis")
    action.add_argument("--repair",        metavar="SYMPTOM_CODE",
                        help="Generate full repair plan for a symptom code")
    action.add_argument("--info",          metavar="ENTITY_ID",
                        help="Look up a system, symptom, or repair by ID")
    action.add_argument("--stats",         metavar="VERSION",
                        help="Print statistics for a version (1, 2, or 3)")
    action.add_argument("--list-versions", action="store_true",
                        help="List all available knowledge base versions")
    action.add_argument("--demo",          action="store_true",
                        help="Run full demo across all versions")

    # ── Options ───────────────────────────────────────────────────────────────
    parser.add_argument("--version",     type=int, choices=[1, 2, 3],
                        help="Restrict to a specific version (1, 2, or 3)")
    parser.add_argument("--top-k",       type=int, default=5, dest="top_k",
                        help="Max results to return (default: 5)")
    parser.add_argument("--entity-type", choices=["system", "symptom", "repair"],
                        dest="entity_type",
                        help="Filter search results to one entity type")
    parser.add_argument("--json",        action="store_true",
                        help="Output raw JSON instead of formatted text")
    parser.add_argument("--versions",    nargs="+",
                        default=["1.0", "2.0", "3.0"],
                        help="Versions to load (default: all)")

    args = parser.parse_args()

    # Demo doesn't need engine loading here (it handles its own)
    if args.demo:
        demo()
        return

    # Determine which versions to load
    if args.version:
        load_versions = [str(float(args.version))]
    else:
        load_versions = args.versions

    # Load engines
    if not args.json:
        print(_dim(f"Loading FixFinder engines ({', '.join(load_versions)}) …"),
              end="", flush=True)

    try:
        ff = FixFinderSystem(versions=load_versions)
    except Exception as exc:
        print()
        print(_red(f"Failed to load engines: {exc}"), file=sys.stderr)
        sys.exit(1)

    if not args.json:
        print(_green(" ready"))

    # Dispatch
    try:
        if args.search:
            _cli_search(args, ff)
        elif args.diagnose:
            _cli_diagnose(args, ff)
        elif args.repair:
            _cli_repair(args, ff)
        elif args.info:
            _cli_info(args, ff)
        elif args.stats:
            _cli_stats(args, ff)
        elif args.list_versions:
            _cli_list_versions(args, ff)
    finally:
        ff.close()


if __name__ == "__main__":
    main()
