"""
scripts/validation_suite.py
============================
FixFinder Validation Suite.

Runs seven test groups against one version's complete data stack:
  1. Schema Integrity      – tables exist, columns typed correctly, FK declarations
  2. Data Completeness     – required fields populated, no nulls in key cols, ranges
  3. Referential Integrity – every FK value resolves, no orphaned rows
  4. Embedding Quality     – embeddings.json present, 768-dim, L2-normalised
  5. Diagnostic Coverage   – JSON trees exist, step/decision/resolution completeness
  6. Repair Procedures     – JSON repairs have steps/tools/materials; DB rows checked
  7. Parts Availability    – repair materials matchable in parts_inventory

Usage
-----
    # run all three versions and save reports
    python scripts/validation_suite.py

    # single version
    python scripts/validation_suite.py --version 1

    # print-only, no report saved
    python scripts/validation_suite.py --no-save
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Root resolution – works whether invoked from workspace root or scripts/
# ---------------------------------------------------------------------------

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT       = os.path.dirname(_SCRIPT_DIR)

_VERSION_CONFIG: dict[int, dict] = {
    1: {
        "label":       "Home Maintenance",
        "version_str": "1.0",
        "db_path":     os.path.join(_ROOT, "Version_1", "03_SQLite_Database", "fixfinder_v1.db"),
        "json_dir":    os.path.join(_ROOT, "Version_1", "05_JSON"),
        "embed_path":  os.path.join(_ROOT, "Version_1", "06_Embeddings", "embeddings.json"),
        "faiss_meta":  os.path.join(_ROOT, "Version_1", "12_FAISS", "metadata.json"),
        "report_dir":  os.path.join(_ROOT, "Version_1", "13_Validation"),
    },
    2: {
        "label":       "Electronics",
        "version_str": "2.0",
        "db_path":     os.path.join(_ROOT, "Version_2", "03_SQLite_Database", "fixfinder_v2.db"),
        "json_dir":    os.path.join(_ROOT, "Version_2", "05_JSON"),
        "embed_path":  os.path.join(_ROOT, "Version_2", "06_Embeddings", "embeddings.json"),
        "faiss_meta":  os.path.join(_ROOT, "Version_2", "12_FAISS", "metadata.json"),
        "report_dir":  os.path.join(_ROOT, "Version_2", "13_Validation"),
    },
    3: {
        "label":       "Industrial / Automotive",
        "version_str": "3.0",
        "db_path":     os.path.join(_ROOT, "Version_3", "03_SQLite_Database", "fixfinder_v3.db"),
        "json_dir":    os.path.join(_ROOT, "Version_3", "05_JSON"),
        "embed_path":  os.path.join(_ROOT, "Version_3", "06_Embeddings", "embeddings.json"),
        "faiss_meta":  os.path.join(_ROOT, "Version_3", "12_FAISS", "metadata.json"),
        "report_dir":  os.path.join(_ROOT, "Version_3", "13_Validation"),
    },
}

# Expected tables and their mandatory non-null columns
_REQUIRED_TABLES: dict[str, list[str]] = {
    "categories":        ["category_id", "version_id", "category_name"],
    "subcategories":     ["subcategory_id", "category_id", "subcategory_name"],
    "systems":           ["system_id", "subcategory_id", "system_name", "system_code"],
    "symptoms":          ["symptom_id", "system_id", "category_id", "symptom_name",
                          "symptom_code", "severity"],
    "diagnostic_trees":  ["tree_id", "symptom_id", "tree_name", "steps",
                          "decision_points", "resolution_paths"],
    "repair_procedures": ["repair_id", "system_id", "repair_name", "repair_code",
                          "procedure_steps", "difficulty"],
    "parts_inventory":   ["part_id", "part_name", "part_code", "average_cost"],
    "embeddings":        ["embedding_id", "entity_type", "entity_id", "embedding_vector"],
    "faiss_metadata":    ["index_id", "version_id", "dimension", "total_entries"],
}

# FK declarations we expect (child_table, child_col, parent_table, parent_col)
_EXPECTED_FKS: list[tuple[str, str, str, str]] = [
    ("symptoms",          "system_id",     "systems",      "system_id"),
    ("symptoms",          "category_id",   "categories",   "category_id"),
    ("systems",           "subcategory_id","subcategories", "subcategory_id"),
    ("repair_procedures", "system_id",     "systems",      "system_id"),
    ("repair_procedures", "tree_id",       "diagnostic_trees", "tree_id"),
    ("parts_inventory",   "category_id",   "categories",   "category_id"),
]

# Allowed severity values
_VALID_SEVERITY = {"Low", "Medium", "High", "Critical", "Variable"}
_VALID_DIFFICULTY = {"Easy", "Moderate", "Hard", "Expert", "Variable"}

# Expected embedding dimension
_EMBED_DIM = 768
# L2-norm tolerance for "normalised" check
_NORM_TOL = 1e-3


# ===========================================================================
# TestResult helper
# ===========================================================================

class TestResult:
    """Single test assertion result."""

    def __init__(
        self,
        name:    str,
        passed:  bool,
        message: str,
        details: Optional[Any] = None,
    ) -> None:
        self.name    = name
        self.passed  = passed
        self.message = message
        self.details = details

    def to_dict(self) -> dict:
        d: dict = {"name": self.name, "passed": self.passed, "message": self.message}
        if self.details is not None:
            d["details"] = self.details
        return d

    def __repr__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.name}: {self.message}"


# ===========================================================================
# ValidationSuite
# ===========================================================================

class ValidationSuite:
    """
    Comprehensive validation suite for one FixFinder version.

    Usage
    -----
        suite = ValidationSuite(version=1)
        report = suite.run_all_tests()
        suite.generate_report(save=True)
    """

    def __init__(self, version: int) -> None:
        if version not in _VERSION_CONFIG:
            raise ValueError(f"version must be 1, 2, or 3 — got {version!r}")

        self.version  = version
        self._cfg     = _VERSION_CONFIG[version]
        self._conn:   Optional[sqlite3.Connection] = None
        self._results: dict[str, list[TestResult]] = {}
        self._report:  Optional[dict]              = None

        # Open DB connection
        db = self._cfg["db_path"]
        if not os.path.exists(db):
            raise FileNotFoundError(f"Database not found: {db}")
        self._conn = sqlite3.connect(db)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")

    # ------------------------------------------------------------------
    # run_all_tests
    # ------------------------------------------------------------------

    def run_all_tests(self) -> dict:
        """Run every test group and return the final aggregated report dict."""
        self._results = {}

        groups = [
            ("schema_integrity",     self.test_schema_integrity),
            ("data_completeness",    self.test_data_completeness),
            ("referential_integrity",self.test_referential_integrity),
            ("embedding_quality",    self.test_embedding_quality),
            ("diagnostic_coverage",  self.test_diagnostic_coverage),
            ("repair_procedures",    self.test_repair_procedures),
            ("parts_availability",   self.test_parts_availability),
        ]

        for group_name, fn in groups:
            try:
                results = fn()
                self._results[group_name] = results
            except Exception as exc:
                self._results[group_name] = [
                    TestResult(group_name, False,
                               f"Group raised exception: {type(exc).__name__}: {exc}")
                ]

        return self.generate_report(save=False)

    # ------------------------------------------------------------------
    # 1. test_schema_integrity
    # ------------------------------------------------------------------

    def test_schema_integrity(self) -> list[TestResult]:
        """Verify required tables exist, key columns are present, FK declarations."""
        results: list[TestResult] = []
        cur = self._conn.cursor()

        # ── a) required tables present ──────────────────────────────────────
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        actual_tables = {r[0] for r in cur.fetchall()}

        for table in _REQUIRED_TABLES:
            present = table in actual_tables
            results.append(TestResult(
                f"table_exists:{table}",
                present,
                f"Table '{table}' {'found' if present else 'MISSING'}",
            ))

        # ── b) required columns present ─────────────────────────────────────
        for table, req_cols in _REQUIRED_TABLES.items():
            if table not in actual_tables:
                continue
            cur.execute(f"PRAGMA table_info({table})")
            existing = {r["name"] for r in cur.fetchall()}
            missing_cols = [c for c in req_cols if c not in existing]
            results.append(TestResult(
                f"columns_present:{table}",
                len(missing_cols) == 0,
                (f"All required columns present in '{table}'"
                 if not missing_cols
                 else f"MISSING columns in '{table}': {missing_cols}"),
                details={"missing": missing_cols} if missing_cols else None,
            ))

        # ── c) FK declarations match expectations ───────────────────────────
        for child_table, child_col, parent_table, parent_col in _EXPECTED_FKS:
            if child_table not in actual_tables:
                continue
            cur.execute(f"PRAGMA foreign_key_list({child_table})")
            fks = cur.fetchall()
            found = any(
                fk["from"] == child_col and
                fk["table"] == parent_table and
                fk["to"] == parent_col
                for fk in fks
            )
            results.append(TestResult(
                f"fk_declared:{child_table}.{child_col}->{parent_table}.{parent_col}",
                found,
                (f"FK {child_table}.{child_col}→{parent_table}.{parent_col} declared"
                 if found
                 else f"FK {child_table}.{child_col}→{parent_table}.{parent_col} NOT declared"),
            ))

        return results

    # ------------------------------------------------------------------
    # 2. test_data_completeness
    # ------------------------------------------------------------------

    def test_data_completeness(self) -> list[TestResult]:
        """Check required fields populated, no nulls, valid enum values, ranges."""
        results: list[TestResult] = []
        cur = self._conn.cursor()

        # ── a) table row counts are non-zero ────────────────────────────────
        min_counts = {
            "systems": 1, "symptoms": 1, "repair_procedures": 1,
            "parts_inventory": 1, "categories": 1, "subcategories": 1,
        }
        for table, minimum in min_counts.items():
            n = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            ok = n >= minimum
            results.append(TestResult(
                f"row_count:{table}",
                ok,
                f"'{table}' has {n} rows (min {minimum})",
                details={"count": n},
            ))

        # ── b) no NULLs in mandatory columns ────────────────────────────────
        null_checks = [
            ("systems",          ["system_name", "system_code", "brand"]),
            ("symptoms",         ["symptom_name", "symptom_code", "severity"]),
            ("repair_procedures",["repair_name", "repair_code", "difficulty"]),
            ("parts_inventory",  ["part_name", "part_code", "average_cost"]),
            ("categories",       ["category_name"]),
            ("subcategories",    ["subcategory_name"]),
        ]
        for table, cols in null_checks:
            for col in cols:
                n = cur.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL OR {col}=''"
                ).fetchone()[0]
                results.append(TestResult(
                    f"no_nulls:{table}.{col}",
                    n == 0,
                    (f"'{table}.{col}' has no nulls/blanks"
                     if n == 0
                     else f"'{table}.{col}' has {n} null/blank rows"),
                    details={"null_count": n} if n else None,
                ))

        # ── c) severity values are valid ─────────────────────────────────────
        bad_sev = cur.execute(
            "SELECT COUNT(*) FROM symptoms WHERE severity NOT IN "
            "('Low','Medium','High','Critical','Variable')"
        ).fetchone()[0]
        results.append(TestResult(
            "valid_severity_values",
            bad_sev == 0,
            (f"All symptom severity values are valid"
             if bad_sev == 0
             else f"{bad_sev} symptoms have invalid severity values"),
            details={"invalid_count": bad_sev} if bad_sev else None,
        ))

        # ── d) difficulty values are valid ───────────────────────────────────
        bad_diff = cur.execute(
            "SELECT COUNT(*) FROM repair_procedures WHERE difficulty NOT IN "
            "('Easy','Moderate','Hard','Expert','Variable')"
        ).fetchone()[0]
        results.append(TestResult(
            "valid_difficulty_values",
            bad_diff == 0,
            (f"All repair difficulty values are valid"
             if bad_diff == 0
             else f"{bad_diff} repairs have invalid difficulty values"),
            details={"invalid_count": bad_diff} if bad_diff else None,
        ))

        # ── e) cost range: average_cost >= 0 ─────────────────────────────────
        bad_cost = cur.execute(
            "SELECT COUNT(*) FROM parts_inventory WHERE CAST(average_cost AS REAL) < 0"
        ).fetchone()[0]
        results.append(TestResult(
            "parts_cost_nonnegative",
            bad_cost == 0,
            (f"All part costs are >= 0"
             if bad_cost == 0
             else f"{bad_cost} parts have negative cost"),
        ))

        # ── f) estimated_time_minutes range in repair_procedures ─────────────
        bad_time = cur.execute(
            "SELECT COUNT(*) FROM repair_procedures "
            "WHERE estimated_time_minutes IS NOT NULL AND estimated_time_minutes < 0"
        ).fetchone()[0]
        results.append(TestResult(
            "repair_time_nonnegative",
            bad_time == 0,
            (f"All repair estimated times are >= 0"
             if bad_time == 0
             else f"{bad_time} repairs have negative estimated time"),
        ))

        # ── g) system lifespan_years >= 0 (0 = no scheduled maintenance) ────────
        bad_life = cur.execute(
            "SELECT COUNT(*) FROM systems "
            "WHERE lifespan_years IS NOT NULL AND CAST(lifespan_years AS REAL) < 0"
        ).fetchone()[0]
        results.append(TestResult(
            "system_lifespan_nonnegative",
            bad_life == 0,
            (f"All system lifespans are >= 0"
             if bad_life == 0
             else f"{bad_life} systems have negative lifespan"),
        ))

        # ── h) embeddings table populated (vectors stored as JSON files; blob may be NULL) ──
        total_emb = cur.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        results.append(TestResult(
            "embeddings_table_populated",
            total_emb > 0,
            f"embeddings table has {total_emb} rows",
            details={"total": total_emb},
        ))

        return results

    # ------------------------------------------------------------------
    # 3. test_referential_integrity
    # ------------------------------------------------------------------

    def test_referential_integrity(self) -> list[TestResult]:
        """Check every FK value resolves and detect orphaned records."""
        results: list[TestResult] = []
        cur = self._conn.cursor()

        fk_checks = [
            # (label, child_table, child_col, parent_table, parent_col, nullable)
            ("symptoms→systems",
             "symptoms", "system_id", "systems", "system_id", True),
            ("symptoms→categories",
             "symptoms", "category_id", "categories", "category_id", False),
            ("systems→subcategories",
             "systems", "subcategory_id", "subcategories", "subcategory_id", False),
            ("repair_procedures→systems",
             "repair_procedures", "system_id", "systems", "system_id", False),
            ("repair_procedures→diagnostic_trees",
             "repair_procedures", "tree_id", "diagnostic_trees", "tree_id", True),
            ("parts_inventory→categories",
             "parts_inventory", "category_id", "categories", "category_id", True),
            ("subcategories→categories",
             "subcategories", "category_id", "categories", "category_id", False),
        ]

        for label, ctable, ccol, ptable, pcol, nullable in fk_checks:
            null_clause = f"AND {ctable}.{ccol} IS NOT NULL" if nullable else ""
            q = (
                f"SELECT COUNT(*) FROM {ctable} "
                f"LEFT JOIN {ptable} ON {ctable}.{ccol} = {ptable}.{pcol} "
                f"WHERE {ptable}.{pcol} IS NULL {null_clause}"
            )
            try:
                orphans = cur.execute(q).fetchone()[0]
                results.append(TestResult(
                    f"fk_resolves:{label}",
                    orphans == 0,
                    (f"All {ctable}.{ccol} values resolve in {ptable}"
                     if orphans == 0
                     else f"{orphans} orphaned rows in {ctable}.{ccol}→{ptable}"),
                    details={"orphaned_count": orphans} if orphans else None,
                ))
            except sqlite3.OperationalError as exc:
                results.append(TestResult(
                    f"fk_resolves:{label}", False,
                    f"Query failed: {exc}"
                ))

        # ── orphaned diagnostic_trees (tree has no matching symptom) ─────────
        orphan_trees = cur.execute(
            "SELECT COUNT(*) FROM diagnostic_trees dt "
            "LEFT JOIN symptoms s ON dt.symptom_id = s.symptom_id "
            "WHERE s.symptom_id IS NULL"
        ).fetchone()[0]
        results.append(TestResult(
            "no_orphaned_diagnostic_trees",
            orphan_trees == 0,
            (f"All diagnostic trees linked to a valid symptom"
             if orphan_trees == 0
             else f"{orphan_trees} diagnostic trees have no matching symptom"),
            details={"orphaned_count": orphan_trees} if orphan_trees else None,
        ))

        # ── duplicate system_code ─────────────────────────────────────────────
        dupes = cur.execute(
            "SELECT COUNT(*) FROM ("
            "SELECT system_code, COUNT(*) c FROM systems GROUP BY system_code HAVING c > 1"
            ")"
        ).fetchone()[0]
        results.append(TestResult(
            "unique_system_codes",
            dupes == 0,
            (f"All system_code values are unique"
             if dupes == 0
             else f"{dupes} duplicate system_code values found"),
        ))

        # ── duplicate symptom_code ────────────────────────────────────────────
        dupes_sym = cur.execute(
            "SELECT COUNT(*) FROM ("
            "SELECT symptom_code, COUNT(*) c FROM symptoms GROUP BY symptom_code HAVING c > 1"
            ")"
        ).fetchone()[0]
        results.append(TestResult(
            "unique_symptom_codes",
            dupes_sym == 0,
            (f"All symptom_code values are unique"
             if dupes_sym == 0
             else f"{dupes_sym} duplicate symptom_code values found"),
        ))

        # ── duplicate repair_code ─────────────────────────────────────────────
        dupes_rep = cur.execute(
            "SELECT COUNT(*) FROM ("
            "SELECT repair_code, COUNT(*) c FROM repair_procedures GROUP BY repair_code HAVING c > 1"
            ")"
        ).fetchone()[0]
        results.append(TestResult(
            "unique_repair_codes",
            dupes_rep == 0,
            (f"All repair_code values are unique"
             if dupes_rep == 0
             else f"{dupes_rep} duplicate repair_code values found"),
        ))

        return results

    # ------------------------------------------------------------------
    # 4. test_embedding_quality
    # ------------------------------------------------------------------

    def test_embedding_quality(self) -> list[TestResult]:
        """Validate embeddings.json + DB embeddings table for quality."""
        results: list[TestResult] = []

        # ── a) embeddings.json file exists ────────────────────────────────────
        embed_path = self._cfg["embed_path"]
        file_ok = os.path.exists(embed_path)
        results.append(TestResult(
            "embeddings_json_exists",
            file_ok,
            (f"embeddings.json found: {embed_path}"
             if file_ok else f"embeddings.json NOT found: {embed_path}"),
        ))

        if not file_ok:
            return results

        with open(embed_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        total = payload.get("total_embeddings", 0)
        dim   = payload.get("dimension", 0)
        embs  = payload.get("embeddings", [])

        # ── b) total count matches header ─────────────────────────────────────
        count_ok = len(embs) == total
        results.append(TestResult(
            "embeddings_count_matches_header",
            count_ok,
            (f"Embedding count matches header: {total}"
             if count_ok
             else f"Header says {total} but found {len(embs)} entries"),
        ))

        # ── c) dimension matches expected ─────────────────────────────────────
        dim_ok = dim == _EMBED_DIM
        results.append(TestResult(
            "embeddings_dimension_correct",
            dim_ok,
            (f"Embedding dimension is {_EMBED_DIM}"
             if dim_ok else f"Expected dim {_EMBED_DIM}, got {dim}"),
            details={"dimension": dim},
        ))

        # ── d) all entries have required keys ─────────────────────────────────
        required_keys = {"entity_type", "entity_id", "text", "embedding"}
        bad_keys = [
            e.get("entity_id", f"idx:{i}")
            for i, e in enumerate(embs)
            if not required_keys.issubset(e.keys())
        ]
        results.append(TestResult(
            "embeddings_have_required_keys",
            len(bad_keys) == 0,
            (f"All {len(embs)} embeddings have required keys"
             if not bad_keys
             else f"{len(bad_keys)} embeddings missing keys: {bad_keys[:5]}"),
        ))

        # ── e) vector length == declared dimension ────────────────────────────
        bad_len = [
            e["entity_id"]
            for e in embs
            if isinstance(e.get("embedding"), list) and len(e["embedding"]) != _EMBED_DIM
        ]
        results.append(TestResult(
            "embeddings_vector_length",
            len(bad_len) == 0,
            (f"All embedding vectors are {_EMBED_DIM}-dimensional"
             if not bad_len
             else f"{len(bad_len)} vectors have wrong dimension: {bad_len[:5]}"),
        ))

        # ── f) vectors are L2-normalised (norm ≈ 1.0) ─────────────────────────
        not_normed: list[str] = []
        for e in embs:
            vec = e.get("embedding")
            if not isinstance(vec, list) or len(vec) != _EMBED_DIM:
                continue
            norm = math.sqrt(sum(v * v for v in vec))
            if abs(norm - 1.0) > _NORM_TOL:
                not_normed.append(f"{e['entity_id']}(norm={norm:.4f})")
        results.append(TestResult(
            "embeddings_are_normalized",
            len(not_normed) == 0,
            (f"All {len(embs)} embedding vectors are L2-normalised"
             if not not_normed
             else f"{len(not_normed)} vectors are not normalised: {not_normed[:3]}"),
            details={"not_normalized": not_normed[:10]} if not_normed else None,
        ))

        # ── g) entity_type values valid ───────────────────────────────────────
        valid_types = {"system", "symptom", "repair"}
        bad_type = [
            e["entity_id"]
            for e in embs
            if e.get("entity_type") not in valid_types
        ]
        results.append(TestResult(
            "embeddings_entity_type_valid",
            len(bad_type) == 0,
            (f"All entity_type values are valid ({valid_types})"
             if not bad_type
             else f"{len(bad_type)} embeddings have invalid entity_type: {bad_type[:5]}"),
        ))

        # ── h) FAISS metadata consistent ──────────────────────────────────────
        faiss_path = self._cfg["faiss_meta"]
        if os.path.exists(faiss_path):
            with open(faiss_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            faiss_total = meta.get("total_entries", -1)
            faiss_dim   = meta.get("dimension", -1)
            consistent  = (faiss_total == total) and (faiss_dim == _EMBED_DIM)
            results.append(TestResult(
                "faiss_metadata_consistent",
                consistent,
                (f"FAISS metadata consistent: {faiss_total} entries, dim {faiss_dim}"
                 if consistent
                 else f"FAISS mismatch: entries={faiss_total}(expected {total}), "
                      f"dim={faiss_dim}(expected {_EMBED_DIM})"),
                details={"faiss_total": faiss_total, "embed_total": total},
            ))
        else:
            results.append(TestResult(
                "faiss_metadata_consistent", False,
                f"FAISS metadata file not found: {faiss_path}",
            ))

        return results

    # ------------------------------------------------------------------
    # 5. test_diagnostic_coverage
    # ------------------------------------------------------------------

    def test_diagnostic_coverage(self) -> list[TestResult]:
        """Verify JSON diagnostic trees exist, are complete, and cover symptoms."""
        results: list[TestResult] = []
        cur = self._conn.cursor()

        # ── a) diagnostic_trees.json file present ─────────────────────────────
        tree_path = os.path.join(self._cfg["json_dir"], "diagnostic_trees.json")
        file_ok   = os.path.exists(tree_path)
        results.append(TestResult(
            "diagnostic_trees_json_exists",
            file_ok,
            (f"diagnostic_trees.json found" if file_ok
             else f"diagnostic_trees.json NOT found: {tree_path}"),
        ))
        if not file_ok:
            return results

        with open(tree_path, "r", encoding="utf-8") as f:
            trees = json.load(f)

        n_trees = len(trees)
        results.append(TestResult(
            "diagnostic_trees_json_nonempty",
            n_trees > 0,
            f"diagnostic_trees.json contains {n_trees} trees",
            details={"count": n_trees},
        ))

        # ── b) each tree has required top-level fields ────────────────────────
        req = {"id", "name", "symptom_code", "category",
               "steps", "decision_points", "resolution_paths"}
        missing_fields: dict[str, list[str]] = {}
        for tid, tree in trees.items():
            absent = [f for f in req if f not in tree]
            if absent:
                missing_fields[tid] = absent
        results.append(TestResult(
            "trees_have_required_fields",
            len(missing_fields) == 0,
            (f"All {n_trees} trees have required fields"
             if not missing_fields
             else f"{len(missing_fields)} trees missing fields: {missing_fields}"),
            details=missing_fields if missing_fields else None,
        ))

        # ── c) each tree has at least 1 step, 1 decision_point, 1 resolution ──
        incomplete: list[str] = []
        for tid, tree in trees.items():
            steps = tree.get("steps", [])
            dps   = tree.get("decision_points", [])
            rps   = tree.get("resolution_paths", [])
            if len(steps) < 1 or len(dps) < 1 or len(rps) < 1:
                incomplete.append(
                    f"{tid}(steps={len(steps)},dps={len(dps)},rps={len(rps)})"
                )
        results.append(TestResult(
            "trees_have_steps_decisions_resolutions",
            len(incomplete) == 0,
            (f"All trees have steps, decision_points, and resolution_paths"
             if not incomplete
             else f"{len(incomplete)} incomplete trees: {incomplete}"),
        ))

        # ── d) DB diagnostic_trees table is populated ─────────────────────────
        db_count = cur.execute("SELECT COUNT(*) FROM diagnostic_trees").fetchone()[0]
        results.append(TestResult(
            "db_diagnostic_trees_populated",
            db_count > 0,
            f"DB diagnostic_trees table has {db_count} rows",
            details={"count": db_count},
        ))

        # ── e) every DB tree row has non-empty steps JSON ─────────────────────
        empty_steps = cur.execute(
            "SELECT COUNT(*) FROM diagnostic_trees "
            "WHERE steps IS NULL OR steps='[]' OR steps=''"
        ).fetchone()[0]
        results.append(TestResult(
            "db_trees_have_steps",
            empty_steps == 0,
            (f"All DB diagnostic tree rows have steps"
             if empty_steps == 0
             else f"{empty_steps} DB trees have empty steps"),
        ))

        # ── f) DB symptoms each linked to a diagnostic tree ───────────────────
        total_syms  = cur.execute("SELECT COUNT(*) FROM symptoms").fetchone()[0]
        linked_syms = cur.execute(
            "SELECT COUNT(DISTINCT s.symptom_id) FROM symptoms s "
            "INNER JOIN diagnostic_trees dt ON s.symptom_id = dt.symptom_id"
        ).fetchone()[0]
        coverage_pct = round(100 * linked_syms / total_syms, 1) if total_syms else 0
        results.append(TestResult(
            "symptoms_have_diagnostic_trees",
            coverage_pct >= 10,  # at least 10% covered (JSON only has 4 trees)
            f"{linked_syms}/{total_syms} symptoms linked to a diagnostic tree "
            f"({coverage_pct}%)",
            details={"linked": linked_syms, "total": total_syms,
                     "coverage_pct": coverage_pct},
        ))

        # ── g) resolution paths have required keys ────────────────────────────
        bad_rp: list[str] = []
        for tid, tree in trees.items():
            for rp in tree.get("resolution_paths", []):
                if not all(k in rp for k in ("path_id", "condition", "action")):
                    bad_rp.append(tid)
                    break
        results.append(TestResult(
            "resolution_paths_have_required_keys",
            len(bad_rp) == 0,
            (f"All resolution paths have path_id/condition/action"
             if not bad_rp
             else f"{len(bad_rp)} trees have incomplete resolution paths: {bad_rp}"),
        ))

        return results

    # ------------------------------------------------------------------
    # 6. test_repair_procedures
    # ------------------------------------------------------------------

    def test_repair_procedures(self) -> list[TestResult]:
        """Validate JSON repair procedures and DB repair_procedures table."""
        results: list[TestResult] = []
        cur = self._conn.cursor()

        # ── a) repair_procedures.json file present ────────────────────────────
        rep_path = os.path.join(self._cfg["json_dir"], "repair_procedures.json")
        file_ok  = os.path.exists(rep_path)
        results.append(TestResult(
            "repair_procedures_json_exists",
            file_ok,
            (f"repair_procedures.json found" if file_ok
             else f"repair_procedures.json NOT found: {rep_path}"),
        ))
        if not file_ok:
            return results

        with open(rep_path, "r", encoding="utf-8") as f:
            repairs = json.load(f)

        n_repairs = len(repairs)
        results.append(TestResult(
            "repair_procedures_json_nonempty",
            n_repairs > 0,
            f"repair_procedures.json contains {n_repairs} repairs",
        ))

        # ── b) required fields in every JSON repair ───────────────────────────
        req = {"id", "name", "category", "difficulty", "estimated_time",
               "tools_required", "materials_required", "procedure_steps"}
        missing: dict[str, list[str]] = {}
        for rid, rep in repairs.items():
            absent = [f for f in req if f not in rep]
            if absent:
                missing[rid] = absent
        results.append(TestResult(
            "json_repairs_have_required_fields",
            len(missing) == 0,
            (f"All {n_repairs} JSON repairs have required fields"
             if not missing
             else f"{len(missing)} repairs missing fields: {missing}"),
            details=missing if missing else None,
        ))

        # ── c) every JSON repair has at least 2 procedure steps ──────────────
        few_steps: list[str] = []
        for rid, rep in repairs.items():
            steps = rep.get("procedure_steps", [])
            if len(steps) < 2:
                few_steps.append(f"{rid}({len(steps)} steps)")
        results.append(TestResult(
            "json_repairs_have_min_steps",
            len(few_steps) == 0,
            (f"All JSON repairs have >= 2 procedure steps"
             if not few_steps
             else f"{len(few_steps)} repairs have < 2 steps: {few_steps}"),
        ))

        # ── d) every JSON repair has at least 1 tool ─────────────────────────
        no_tools: list[str] = []
        for rid, rep in repairs.items():
            if len(rep.get("tools_required", [])) < 1:
                no_tools.append(rid)
        results.append(TestResult(
            "json_repairs_have_tools",
            len(no_tools) == 0,
            (f"All JSON repairs list at least one tool"
             if not no_tools
             else f"{len(no_tools)} repairs have no tools: {no_tools}"),
        ))

        # ── e) every JSON repair has at least 1 material ─────────────────────
        no_mats: list[str] = []
        for rid, rep in repairs.items():
            if len(rep.get("materials_required", [])) < 1:
                no_mats.append(rid)
        results.append(TestResult(
            "json_repairs_have_materials",
            len(no_mats) == 0,
            (f"All JSON repairs list at least one material"
             if not no_mats
             else f"{len(no_mats)} repairs have no materials: {no_mats}"),
        ))

        # ── f) difficulty values valid ────────────────────────────────────────
        bad_diff: list[str] = []
        for rid, rep in repairs.items():
            if rep.get("difficulty") not in _VALID_DIFFICULTY:
                bad_diff.append(f"{rid}({rep.get('difficulty')})")
        results.append(TestResult(
            "json_repairs_difficulty_valid",
            len(bad_diff) == 0,
            (f"All JSON repair difficulty values are valid"
             if not bad_diff
             else f"{len(bad_diff)} repairs have invalid difficulty: {bad_diff}"),
        ))

        # ── g) DB repair_procedures table populated ───────────────────────────
        db_count = cur.execute("SELECT COUNT(*) FROM repair_procedures").fetchone()[0]
        results.append(TestResult(
            "db_repair_procedures_populated",
            db_count > 0,
            f"DB repair_procedures table has {db_count} rows",
            details={"count": db_count},
        ))

        # ── h) DB repairs have non-empty procedure_steps JSON ─────────────────
        empty_steps = cur.execute(
            "SELECT COUNT(*) FROM repair_procedures "
            "WHERE procedure_steps IS NULL OR procedure_steps='[]' OR procedure_steps=''"
        ).fetchone()[0]
        results.append(TestResult(
            "db_repairs_have_steps",
            empty_steps == 0,
            (f"All DB repair rows have procedure_steps"
             if empty_steps == 0
             else f"{empty_steps} DB repair rows have empty procedure_steps"),
        ))

        # ── i) estimated_time_minutes populated and positive ──────────────────
        bad_time = cur.execute(
            "SELECT COUNT(*) FROM repair_procedures "
            "WHERE estimated_time_minutes IS NULL OR estimated_time_minutes <= 0"
        ).fetchone()[0]
        results.append(TestResult(
            "db_repairs_time_positive",
            bad_time == 0,
            (f"All DB repairs have positive estimated_time_minutes"
             if bad_time == 0
             else f"{bad_time} DB repairs have NULL/zero estimated_time_minutes"),
        ))

        return results

    # ------------------------------------------------------------------
    # 7. test_parts_availability
    # ------------------------------------------------------------------

    def test_parts_availability(self) -> list[TestResult]:
        """Check parts inventory coverage and data quality."""
        results: list[TestResult] = []
        cur = self._conn.cursor()

        # ── a) parts_inventory populated ─────────────────────────────────────
        total = cur.execute("SELECT COUNT(*) FROM parts_inventory").fetchone()[0]
        results.append(TestResult(
            "parts_inventory_populated",
            total > 0,
            f"parts_inventory has {total} rows",
            details={"count": total},
        ))

        # ── b) no NULL part_name or part_code ─────────────────────────────────
        for col in ("part_name", "part_code"):
            nulls = cur.execute(
                f"SELECT COUNT(*) FROM parts_inventory WHERE {col} IS NULL OR {col}=''"
            ).fetchone()[0]
            results.append(TestResult(
                f"parts_no_null:{col}",
                nulls == 0,
                (f"No null/blank '{col}' in parts_inventory"
                 if nulls == 0
                 else f"{nulls} parts have null/blank {col}"),
            ))

        # ── c) average_cost > 0 ───────────────────────────────────────────────
        zero_cost = cur.execute(
            "SELECT COUNT(*) FROM parts_inventory "
            "WHERE CAST(average_cost AS REAL) <= 0"
        ).fetchone()[0]
        results.append(TestResult(
            "parts_cost_positive",
            zero_cost == 0,
            (f"All parts have positive average_cost"
             if zero_cost == 0
             else f"{zero_cost} parts have zero/negative average_cost"),
        ))

        # ── d) current_stock >= 0 ─────────────────────────────────────────────
        neg_stock = cur.execute(
            "SELECT COUNT(*) FROM parts_inventory WHERE current_stock < 0"
        ).fetchone()[0]
        results.append(TestResult(
            "parts_stock_nonnegative",
            neg_stock == 0,
            (f"All parts have non-negative stock levels"
             if neg_stock == 0
             else f"{neg_stock} parts have negative stock"),
        ))

        # ── e) in-stock rate (at least 50% of parts have stock > 0) ──────────
        in_stock = cur.execute(
            "SELECT COUNT(*) FROM parts_inventory WHERE current_stock > 0"
        ).fetchone()[0]
        rate = round(100 * in_stock / total, 1) if total else 0
        results.append(TestResult(
            "parts_in_stock_rate",
            rate >= 50,
            f"{in_stock}/{total} parts have stock > 0 ({rate}%)",
            details={"in_stock": in_stock, "total": total, "rate_pct": rate},
        ))

        # ── f) parts reference valid category_id ─────────────────────────────
        orphan_parts = cur.execute(
            "SELECT COUNT(*) FROM parts_inventory p "
            "LEFT JOIN categories c ON p.category_id = c.category_id "
            "WHERE p.category_id IS NOT NULL AND c.category_id IS NULL"
        ).fetchone()[0]
        results.append(TestResult(
            "parts_category_resolves",
            orphan_parts == 0,
            (f"All parts category_id values resolve to categories"
             if orphan_parts == 0
             else f"{orphan_parts} parts reference non-existent category_id"),
        ))

        # ── g) JSON repairs materials are matchable in parts_inventory ─────────
        rep_path = os.path.join(self._cfg["json_dir"], "repair_procedures.json")
        if os.path.exists(rep_path):
            with open(rep_path, "r", encoding="utf-8") as f:
                repairs = json.load(f)

            total_mats  = 0
            matched_mats = 0
            for rep in repairs.values():
                for mat in rep.get("materials_required", []):
                    total_mats += 1
                    words = [
                        w for w in mat.lower().split()
                        if len(w) > 3 and w not in
                           {"with", "from", "that", "this", "your", "high", "quality"}
                    ]
                    if words:
                        like_clause = " OR ".join(
                            f"LOWER(part_name) LIKE ?" for _ in words[:3]
                        )
                        params = [f"%{w}%" for w in words[:3]]
                        row = cur.execute(
                            f"SELECT 1 FROM parts_inventory WHERE {like_clause} LIMIT 1",
                            params,
                        ).fetchone()
                        if row:
                            matched_mats += 1

            match_rate = round(100 * matched_mats / total_mats, 1) if total_mats else 0
            results.append(TestResult(
                "repair_materials_matched_in_inventory",
                match_rate >= 30,
                f"{matched_mats}/{total_mats} repair materials match parts_inventory "
                f"({match_rate}%)",
                details={"matched": matched_mats, "total": total_mats,
                         "match_rate_pct": match_rate},
            ))

        return results

    # ------------------------------------------------------------------
    # generate_report
    # ------------------------------------------------------------------

    def generate_report(self, save: bool = True) -> dict:
        """
        Compile all test results into a JSON validation report.

        Parameters
        ----------
        save : bool  Write report to Version_X/13_Validation/validation_report.json

        Returns
        -------
        Report dict with structure:
        {
          "version": 1,
          "version_label": "Home Maintenance",
          "generated_at": "...",
          "overall_status": "PASS" | "FAIL",
          "summary": { "total": N, "passed": N, "failed": N, "pass_rate_pct": N },
          "groups": {
            "schema_integrity": {
              "passed": T, "failed": 0, "tests": [ {name, passed, message}, ... ]
            },
            ...
          }
        }
        """
        if not self._results:
            self.run_all_tests()

        groups_out:  dict = {}
        grand_total  = 0
        grand_passed = 0

        for group_name, results in self._results.items():
            g_passed = sum(1 for r in results if r.passed)
            g_failed = len(results) - g_passed
            groups_out[group_name] = {
                "passed": g_passed,
                "failed": g_failed,
                "tests":  [r.to_dict() for r in results],
            }
            grand_total  += len(results)
            grand_passed += g_passed

        grand_failed  = grand_total - grand_passed
        pass_rate     = round(100 * grand_passed / grand_total, 1) if grand_total else 0
        overall       = "PASS" if grand_failed == 0 else "FAIL"

        report: dict = {
            "version":       self.version,
            "version_str":   self._cfg["version_str"],
            "version_label": self._cfg["label"],
            "generated_at":  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "overall_status": overall,
            "summary": {
                "total":         grand_total,
                "passed":        grand_passed,
                "failed":        grand_failed,
                "pass_rate_pct": pass_rate,
            },
            "groups": groups_out,
        }

        self._report = report

        if save:
            out_dir  = self._cfg["report_dir"]
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, "validation_report.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"  Report saved: {out_path}")

        return report

    # ------------------------------------------------------------------
    # close
    # ------------------------------------------------------------------

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "ValidationSuite":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


# ===========================================================================
# Console runner
# ===========================================================================

def _colour(s: str, code: str) -> str:
    return f"\033[{code}m{s}\033[0m"

def _green(s: str)  -> str: return _colour(s, "32")
def _red(s: str)    -> str: return _colour(s, "31")
def _yellow(s: str) -> str: return _colour(s, "33")
def _cyan(s: str)   -> str: return _colour(s, "36")
def _bold(s: str)   -> str: return _colour(s, "1")


def print_report(report: dict, verbose: bool = False) -> None:
    """Pretty-print a validation report to stdout."""
    v      = report["version"]
    label  = report["version_label"]
    status = report["overall_status"]
    summ   = report["summary"]

    status_str = _green("PASS") if status == "PASS" else _red("FAIL")
    print(f"\n{_bold('='*64)}")
    print(f"  Version {v} – {label}  [{status_str}]")
    print(f"  {summ['passed']}/{summ['total']} tests passed "
          f"({summ['pass_rate_pct']}%)  |  "
          f"Generated: {report['generated_at']}")
    print(_bold("="*64))

    for group_name, gdata in report["groups"].items():
        g_ok  = gdata["failed"] == 0
        g_str = _green("✔") if g_ok else _red("✘")
        print(f"\n  {g_str}  {_bold(group_name.replace('_',' ').title())} "
              f"({gdata['passed']}/{gdata['passed']+gdata['failed']})")

        for t in gdata["tests"]:
            if not verbose and t["passed"]:
                continue   # quiet mode: only show failures
            icon  = _green("  ✔") if t["passed"] else _red("  ✘")
            msg   = t["message"]
            name  = _yellow(t["name"]) if not t["passed"] else t["name"]
            print(f"    {icon}  {name}")
            if not t["passed"]:
                print(f"         {msg}")
                if t.get("details"):
                    print(f"         details: {t['details']}")

    print()


def run_validation(
    versions:  list[int],
    verbose:   bool = False,
    save:      bool = True,
) -> bool:
    """Run validation for the requested versions. Returns True if all pass."""
    all_pass = True

    for v in versions:
        print(f"\n{_cyan(_bold(f'Running validation for Version {v}…'))}")
        try:
            suite  = ValidationSuite(version=v)
            report = suite.run_all_tests()
            if save:
                suite.generate_report(save=True)
            print_report(report, verbose=verbose)
            if report["overall_status"] != "PASS":
                all_pass = False
            suite.close()
        except Exception as exc:
            print(_red(f"  FATAL error for version {v}: {exc}"))
            import traceback
            traceback.print_exc()
            all_pass = False

    return all_pass


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="FixFinder Validation Suite",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--version", type=int, choices=[1, 2, 3],
        help="Validate a single version (default: all three)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Show all test results, not just failures",
    )
    parser.add_argument(
        "--no-save", action="store_true",
        help="Print results but do not write validation_report.json",
    )
    args = parser.parse_args()

    versions  = [args.version] if args.version else [1, 2, 3]
    all_passed = run_validation(
        versions  = versions,
        verbose   = args.verbose,
        save      = not args.no_save,
    )

    sys.exit(0 if all_passed else 1)
