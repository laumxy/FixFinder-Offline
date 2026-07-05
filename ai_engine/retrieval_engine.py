"""
ai_engine/retrieval_engine.py
==============================
FixFinder AI Retrieval Engine.

Combines:
  • Deterministic SHA-256 synthetic embedding generation (same algo as
    generate_embeddings.py, so query vectors are in the same space as
    the stored index vectors).
  • FAISS IndexFlatIP for cosine-similarity retrieval.
  • SQLite queries against the per-version fixfinder_vX.db database for
    rich entity detail (systems, symptoms, repair procedures).

Usage
-----
    from ai_engine.retrieval_engine import AIRetrievalEngine

    engine = AIRetrievalEngine(version=1)
    results = engine.search("roof leaking near chimney", top_k=5)
    for r in results:
        print(r["rank"], r["entity_id"], r["score"], r["entity_type"])

    sys_info  = engine.get_system_details("ROF-001")
    sym_info  = engine.get_symptom_details("PRB-ROF-002")
    rep_info  = engine.get_repair_procedure("RP-ROF-001")
    engine.close()
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from typing import Any, Optional

import faiss
import numpy as np

# ---------------------------------------------------------------------------
# Base paths (resolved relative to this file's parent directory)
# ---------------------------------------------------------------------------

_HERE     = os.path.dirname(os.path.abspath(__file__))
_ROOT     = os.path.dirname(_HERE)   # workspace root

_VERSION_CONFIG = {
    1: {
        "label":       "Home Maintenance",
        "faiss_dir":   os.path.join(_ROOT, "Version_1", "12_FAISS"),
        "db_path":     os.path.join(_ROOT, "Version_1", "03_SQLite_Database", "fixfinder_v1.db"),
        "embed_path":  os.path.join(_ROOT, "Version_1", "06_Embeddings", "embeddings.json"),
    },
    2: {
        "label":       "Electronics",
        "faiss_dir":   os.path.join(_ROOT, "Version_2", "12_FAISS"),
        "db_path":     os.path.join(_ROOT, "Version_2", "03_SQLite_Database", "fixfinder_v2.db"),
        "embed_path":  os.path.join(_ROOT, "Version_2", "06_Embeddings", "embeddings.json"),
    },
    3: {
        "label":       "Industrial / Automotive",
        "faiss_dir":   os.path.join(_ROOT, "Version_3", "12_FAISS"),
        "db_path":     os.path.join(_ROOT, "Version_3", "03_SQLite_Database", "fixfinder_v3.db"),
        "embed_path":  os.path.join(_ROOT, "Version_3", "06_Embeddings", "embeddings.json"),
    },
}

# Entity-type classifier: maps first segment of entity_id → entity_type string
_SYSTEM_PREFIXES: set[str] = {
    "ROF", "FND", "PLM", "ELC", "HVC", "EXT", "WIN", "GRG", "SMP",
    "PHN", "TAB", "LAP", "DKT", "TV",  "AUD", "CAM", "NET", "GAM", "WRB",
    "CAR", "TRK", "MCY", "HVY", "GEN", "CMP", "PMP", "MOT", "VAN", "SUV", "EV",
}

_DIMENSION = 768


# ===========================================================================
# AIRetrievalEngine
# ===========================================================================

class AIRetrievalEngine:
    """
    End-to-end retrieval engine for a single FixFinder version.

    Lifecycle
    ---------
    1. Instantiate with ``AIRetrievalEngine(version=1|2|3)``.
    2. Call ``search()``, ``get_system_details()``, etc.
    3. Call ``close()`` when done (or use as a context manager).

    The engine loads the FAISS index, metadata, and opens the SQLite
    connection lazily on first access.  All resources are freed by
    ``close()``.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, version: int) -> None:
        if version not in _VERSION_CONFIG:
            raise ValueError(f"version must be 1, 2, or 3 — got {version!r}")
        self.version    = version
        self._cfg       = _VERSION_CONFIG[version]
        self._dimension = _DIMENSION

        # Loaded on first use
        self._faiss_index:  Optional[faiss.IndexFlatIP] = None
        self._id_mapping:   Optional[dict[str, str]]    = None  # {"0": "ROF-001", ...}
        self._rev_mapping:  Optional[dict[str, int]]    = None  # {"ROF-001": 0, ...}
        self._faiss_meta:   Optional[dict]              = None
        self._db_conn:      Optional[sqlite3.Connection] = None

        # Pre-load both on construction for fail-fast behaviour
        self.load_version(self._cfg)

    # ------------------------------------------------------------------
    # load_version
    # ------------------------------------------------------------------

    def load_version(self, version_path: dict) -> None:
        """
        Load FAISS index + metadata and open the SQLite connection.

        Parameters
        ----------
        version_path : dict
            The config entry from ``_VERSION_CONFIG``, containing keys:
            ``faiss_dir``, ``db_path``, ``embed_path``, ``label``.
        """
        faiss_dir  = version_path["faiss_dir"]
        index_file = os.path.join(faiss_dir, "index.faiss")
        meta_file  = os.path.join(faiss_dir, "metadata.json")
        db_file    = version_path["db_path"]

        for path in (index_file, meta_file):
            if not os.path.exists(path):
                raise FileNotFoundError(
                    f"FAISS file not found: {path}\n"
                    "Run build_faiss_indices.py first."
                )
        if not os.path.exists(db_file):
            raise FileNotFoundError(
                f"SQLite database not found: {db_file}"
            )

        # ---- FAISS ----
        self._faiss_index = faiss.read_index(index_file)

        with open(meta_file, "r", encoding="utf-8") as f:
            self._faiss_meta = json.load(f)

        self._id_mapping  = self._faiss_meta["id_mapping"]
        self._rev_mapping = {v: int(k) for k, v in self._id_mapping.items()}

        # ---- SQLite ----
        self._db_conn = sqlite3.connect(db_file, check_same_thread=False)
        self._db_conn.row_factory = sqlite3.Row
        self._db_conn.execute("PRAGMA journal_mode=WAL")

    # ------------------------------------------------------------------
    # Synthetic embedding generation  (matches generate_embeddings.py)
    # ------------------------------------------------------------------

    def _generate_synthetic_embedding(self, text: str) -> np.ndarray:
        """
        Produce a deterministic 768-dim L2-normalised float32 vector.

        Algorithm (identical to generate_embeddings.py):
          1. SHA-256 hash the UTF-8 encoded text.
          2. Seed a NumPy RandomState with the first 4 bytes of the digest.
          3. Draw `dimension` standard-normal samples.
          4. L2-normalise.
        """
        digest   = hashlib.sha256(text.encode("utf-8")).digest()
        seed_int = int.from_bytes(digest[:4], "big")
        rng      = np.random.RandomState(seed=seed_int)
        vec      = rng.randn(self._dimension).astype(np.float32)
        norm     = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------

    def search(
        self,
        query_text: str,
        top_k: int = 5,
        entity_type_filter: Optional[str] = None,
    ) -> list[dict]:
        """
        Semantic search over the FAISS index using a free-text query.

        Parameters
        ----------
        query_text          : str   Natural-language query.
        top_k               : int   Maximum results to return (default 5).
        entity_type_filter  : str | None
                              Restrict to "system", "symptom", or "repair".
                              When set, extra candidates are fetched so that
                              ``top_k`` filtered results are returned.

        Returns
        -------
        list of dicts, sorted by descending cosine score:
        [
          {
            "rank":        1,
            "entity_id":   "ROF-001",
            "entity_type": "system",
            "score":       0.1234,
            "faiss_idx":   0,
          },
          ...
        ]
        """
        if not query_text or not query_text.strip():
            raise ValueError("query_text must not be empty.")

        # Generate query embedding (same method as stored vectors)
        q_vec = self._generate_synthetic_embedding(query_text.strip())
        q     = q_vec.reshape(1, -1).copy()        # FAISS needs C-contiguous
        faiss.normalize_L2(q)

        # Fetch more candidates when filtering so we still return top_k
        fetch_k = min(
            top_k * 5 if entity_type_filter else top_k,
            self._faiss_meta["total_entries"],
        )

        scores_arr, indices_arr = self._faiss_index.search(q, fetch_k)
        scores  = scores_arr[0].tolist()
        indices = indices_arr[0].tolist()

        results: list[dict] = []
        for faiss_idx, score in zip(indices, scores):
            if faiss_idx < 0:
                continue
            entity_id   = self._id_mapping.get(str(faiss_idx))
            if entity_id is None:
                continue
            entity_type = self._classify_entity_type(entity_id)

            if entity_type_filter and entity_type != entity_type_filter:
                continue

            results.append({
                "rank":        len(results) + 1,
                "entity_id":   entity_id,
                "entity_type": entity_type,
                "score":       round(float(score), 6),
                "faiss_idx":   int(faiss_idx),
            })
            if len(results) == top_k:
                break

        return results

    # ------------------------------------------------------------------
    # get_system_details
    # ------------------------------------------------------------------

    def get_system_details(self, system_id: str) -> Optional[dict]:
        """
        Fetch full system information from the SQLite database.

        Looks up by ``system_code`` (e.g. "ROF-001") or by numeric
        ``system_id``.  Returns ``None`` if not found.

        Returns
        -------
        dict with keys:
          system_id, system_name, system_code, brand, model,
          year_released, lifespan_years, maintenance_interval_months,
          specifications, components, parts_list, common_issues,
          subcategory, created_at
        """
        self._require_db()
        cur = self._db_conn.cursor()

        # Try matching on system_code first, then on system_name fragment
        row = cur.execute(
            "SELECT s.*, sc.subcategory_name "
            "FROM systems s "
            "LEFT JOIN subcategories sc ON s.subcategory_id = sc.subcategory_id "
            "WHERE s.system_code = ?",
            (system_id,),
        ).fetchone()

        if row is None:
            # fallback: partial case-insensitive name match
            row = cur.execute(
                "SELECT s.*, sc.subcategory_name "
                "FROM systems s "
                "LEFT JOIN subcategories sc ON s.subcategory_id = sc.subcategory_id "
                "WHERE UPPER(s.system_name) LIKE UPPER(?)",
                (f"%{system_id}%",),
            ).fetchone()

        if row is None:
            return None

        return {
            "system_id":                    row["system_id"],
            "system_name":                  row["system_name"],
            "system_code":                  row["system_code"],
            "brand":                        row["brand"],
            "model":                        row["model"],
            "year_released":                row["year_released"],
            "lifespan_years":               row["lifespan_years"],
            "maintenance_interval_months":  row["maintenance_interval_months"],
            "subcategory":                  row["subcategory_name"],
            "specifications":               self._parse_json(row["specifications"]),
            "components":                   self._parse_json(row["components"]),
            "parts_list":                   self._parse_json(row["parts_list"]),
            "common_issues":                self._parse_json(row["common_issues"]),
            "created_at":                   row["created_at"],
        }

    # ------------------------------------------------------------------
    # get_symptom_details
    # ------------------------------------------------------------------

    def get_symptom_details(self, symptom_id: str) -> Optional[dict]:
        """
        Fetch full symptom information from the SQLite database.

        Looks up by ``symptom_code`` (e.g. "PRB-ROF-002") or partial
        ``symptom_name`` match.  Returns ``None`` if not found.

        Returns
        -------
        dict with keys:
          symptom_id, symptom_name, symptom_code, severity, description,
          causes, diagnostic_time_minutes, difficulty,
          parts_needed, tools_needed, system_name, created_at
        """
        self._require_db()
        cur = self._db_conn.cursor()

        row = cur.execute(
            "SELECT sym.*, sys.system_name "
            "FROM symptoms sym "
            "LEFT JOIN systems sys ON sym.system_id = sys.system_id "
            "WHERE sym.symptom_code = ?",
            (symptom_id,),
        ).fetchone()

        if row is None:
            row = cur.execute(
                "SELECT sym.*, sys.system_name "
                "FROM symptoms sym "
                "LEFT JOIN systems sys ON sym.system_id = sys.system_id "
                "WHERE UPPER(sym.symptom_name) LIKE UPPER(?)",
                (f"%{symptom_id}%",),
            ).fetchone()

        if row is None:
            return None

        return {
            "symptom_id":               row["symptom_id"],
            "symptom_name":             row["symptom_name"],
            "symptom_code":             row["symptom_code"],
            "severity":                 row["severity"],
            "description":              row["description"],
            "causes":                   self._parse_json(row["common_causes"]),
            "diagnostic_time_minutes":  row["diagnostic_time_minutes"],
            "difficulty":               row["difficulty"],
            "parts_needed":             self._parse_json(row["parts_needed"]),
            "tools_needed":             self._parse_json(row["tools_needed"]),
            "associated_system":        row["system_name"],
            "created_at":               row["created_at"],
        }

    # ------------------------------------------------------------------
    # get_repair_procedure
    # ------------------------------------------------------------------

    def get_repair_procedure(self, repair_id: str) -> Optional[dict]:
        """
        Fetch a full repair procedure from the SQLite database.

        Looks up by ``repair_code`` (e.g. "RP-ROF-001") or partial
        ``repair_name`` match.  Returns ``None`` if not found.

        Returns
        -------
        dict with keys:
          repair_id, repair_name, repair_code, overview,
          tools_required, materials_required,
          pre_repair_checks, procedure_steps, post_repair_checks,
          estimated_time_minutes, difficulty, warnings, safety_notes,
          system_name, created_at
        """
        self._require_db()
        cur = self._db_conn.cursor()

        row = cur.execute(
            "SELECT rp.*, sys.system_name "
            "FROM repair_procedures rp "
            "LEFT JOIN systems sys ON rp.system_id = sys.system_id "
            "WHERE rp.repair_code = ?",
            (repair_id,),
        ).fetchone()

        if row is None:
            row = cur.execute(
                "SELECT rp.*, sys.system_name "
                "FROM repair_procedures rp "
                "LEFT JOIN systems sys ON rp.system_id = sys.system_id "
                "WHERE UPPER(rp.repair_name) LIKE UPPER(?)",
                (f"%{repair_id}%",),
            ).fetchone()

        if row is None:
            return None

        return {
            "repair_id":            row["repair_id"],
            "repair_name":          row["repair_name"],
            "repair_code":          row["repair_code"],
            "overview":             row["overview"],
            "tools_required":       self._parse_json(row["tools_required"]),
            "materials_required":   self._parse_json(row["materials_required"]),
            "pre_repair_checks":    self._parse_json(row["pre_repair_checks"]),
            "procedure_steps":      self._parse_json(row["procedure_steps"]),
            "post_repair_checks":   self._parse_json(row["post_repair_checks"]),
            "estimated_time_minutes": row["estimated_time_minutes"],
            "difficulty":           row["difficulty"],
            "warnings":             self._parse_json(row["warnings"]),
            "safety_notes":         row["safety_notes"],
            "associated_system":    row["system_name"],
            "created_at":           row["created_at"],
        }

    # ------------------------------------------------------------------
    # close  /  context manager
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release all held resources (FAISS index, SQLite connection)."""
        if self._db_conn:
            self._db_conn.close()
            self._db_conn = None
        # FAISS index is managed by Python GC; set to None to release sooner
        self._faiss_index = None

    def __enter__(self) -> "AIRetrievalEngine":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        label = self._cfg.get("label", f"v{self.version}")
        total = self._faiss_meta["total_entries"] if self._faiss_meta else "?"
        return (
            f"AIRetrievalEngine(version={self.version}, "
            f"label={label!r}, vectors={total}, dim={self._dimension})"
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_entity_type(entity_id: str) -> str:
        """Return "system", "symptom", or "repair" from an entity_id prefix."""
        first = entity_id.split("-")[0].upper()
        if first == "PRB":
            return "symptom"
        if first == "RP":
            return "repair"
        if first in _SYSTEM_PREFIXES:
            return "system"
        return "unknown"

    @staticmethod
    def _parse_json(value: Any) -> Any:
        """Safely parse a JSON string column; return as-is if already parsed."""
        if value is None:
            return None
        if isinstance(value, (list, dict)):
            return value
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    def _require_db(self) -> None:
        if self._db_conn is None:
            raise RuntimeError(
                "SQLite connection is closed. "
                "Create a new AIRetrievalEngine instance."
            )
