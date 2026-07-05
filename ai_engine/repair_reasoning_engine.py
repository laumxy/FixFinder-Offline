"""
ai_engine/repair_reasoning_engine.py
======================================
FixFinder AI Repair Reasoning Engine.

Combines:
  • JSON repair_procedures.json loading and symptom-based matching.
  • SQLite parts_inventory queries for live stock and cost data.
  • Complete repair plan generation with time, cost, and parts breakdown.

Usage
-----
    from ai_engine.repair_reasoning_engine import AIRepairReasoningEngine

    with AIRepairReasoningEngine(version=1) as eng:
        recs  = eng.recommend_repair("PRB-ROF-002", diagnostic_result={})
        avail = eng.check_parts_availability(recs[0]["id"])
        plan  = eng.generate_repair_plan("PRB-ROF-002", diagnostic_result={})
        print(plan["summary"])
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

_VERSION_CONFIG: dict[int, dict] = {
    1: {
        "label":    "Home Maintenance",
        "db_path":  os.path.join(_ROOT, "Version_1", "03_SQLite_Database", "fixfinder_v1.db"),
        "json_dir": os.path.join(_ROOT, "Version_1", "05_JSON"),
    },
    2: {
        "label":    "Electronics",
        "db_path":  os.path.join(_ROOT, "Version_2", "03_SQLite_Database", "fixfinder_v2.db"),
        "json_dir": os.path.join(_ROOT, "Version_2", "05_JSON"),
    },
    3: {
        "label":    "Industrial / Automotive",
        "db_path":  os.path.join(_ROOT, "Version_3", "03_SQLite_Database", "fixfinder_v3.db"),
        "json_dir": os.path.join(_ROOT, "Version_3", "05_JSON"),
    },
}

# Difficulty ordering for sorting (Easy first, Expert last)
_DIFFICULTY_ORDER: dict[str, int] = {
    "Easy":     1,
    "Moderate": 2,
    "Hard":     3,
    "Expert":   4,
    "Variable": 5,
}

# Category → keyword mapping used for symptom→repair matching when no
# direct repair_code is embedded in the diagnostic_result
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    # V1 — Home Maintenance
    "Roofing":     ["roof", "shingle", "flashing", "leak", "gutter", "ridge"],
    "Plumbing":    ["water", "pipe", "faucet", "drain", "toilet", "pressure", "heater", "plumb",
                    "pump", "tank", "hose", "valve", "strainer"],
    "Electrical":  ["outlet", "breaker", "circuit", "gfci", "wire", "electric", "panel", "fuse"],
    "HVAC":        ["hvac", "furnace", "heat", "cool", "ac", "filter", "capacitor", "thermostat",
                    "generator", "carburetor", "fuel", "starts", "dies", "stall"],
    "Appliances":  ["fridge", "refrigerator", "propane", "gas", "appliance", "relay", "compressor",
                    "washer", "stove", "oven", "burner", "igniter", "thermocouple", "orifice",
                    "cooling", "absorption", "flue", "pilot", "light"],
    "Foundation":  ["foundation", "crack", "basement", "sump", "water intrusion", "leveling",
                    "hydraulic", "jack", "sensor"],
    "Windows":     ["window", "draft", "seal", "weatherstrip", "glass"],
    "Garage":      ["garage", "door", "spring", "opener", "slide", "awning", "retract",
                    "extend", "motor", "gear", "stuck", "rv"],
    # V2 — Electronics
    "Phones":      ["phone", "iphone", "samsung", "battery", "screen", "charging", "port"],
    "Laptops":     ["laptop", "macbook", "thermal", "overheat", "keyboard", "display", "paste"],
    "Desktops":    ["desktop", "pc", "gpu", "ram", "bsod", "power supply"],
    "TVs":         ["tv", "television", "backlight", "oled", "screen", "picture"],
    "Gaming":      ["ps5", "xbox", "console", "disc", "hdmi", "game"],
    "Networking":  ["router", "wifi", "network", "firmware", "internet"],
    # V3 — Industrial / Automotive
    "Cars":        ["car", "engine", "brake", "o2", "sensor", "spark", "oil", "transmission"],
    "Trucks":      ["truck", "diesel", "smoke", "injector"],
    "Motorcycles": ["motorcycle", "chain", "sprocket", "bike"],
    "Heavy Equipment": ["excavator", "hydraulic", "track", "forklift", "tractor", "heavy"],
    "Generators":  ["generator", "diesel", "fuel", "control panel", "start"],
    "Compressors": ["compressor", "pressure", "air", "valve"],
    "Motors":      ["motor", "bearing", "electric motor", "winding"],
    "Solar Systems": ["solar", "panel", "inverter", "output"],
}


# ===========================================================================
# AIRepairReasoningEngine
# ===========================================================================

class AIRepairReasoningEngine:
    """
    Repair recommendation and plan generation engine for a single FixFinder version.

    Lifecycle
    ---------
    1. ``AIRepairReasoningEngine(version=1|2|3)``
    2. ``recommend_repair(symptom_code, diagnostic_result)``
    3. ``check_parts_availability(repair_id)``
    4. ``generate_repair_plan(symptom_code, diagnostic_result)``
    5. ``close()``

    Use as a context manager for automatic cleanup.
    """

    def __init__(self, version: int) -> None:
        if version not in _VERSION_CONFIG:
            raise ValueError(f"version must be 1, 2, or 3 — got {version!r}")
        self.version = version
        self._cfg    = _VERSION_CONFIG[version]

        self._db_conn:       Optional[sqlite3.Connection] = None
        self._repairs_cache: Optional[dict]               = None   # lazy

        self.load_version(self._cfg)

    # ------------------------------------------------------------------
    # load_version
    # ------------------------------------------------------------------

    def load_version(self, version_path: dict) -> None:
        """
        Open the SQLite connection and validate the JSON repair file exists.

        Parameters
        ----------
        version_path : dict
            Config entry from ``_VERSION_CONFIG`` with ``db_path`` / ``json_dir``.
        """
        db_file   = version_path["db_path"]
        json_dir  = version_path["json_dir"]
        rep_file  = os.path.join(json_dir, "repair_procedures.json")

        if not os.path.exists(db_file):
            raise FileNotFoundError(f"SQLite database not found: {db_file}")
        if not os.path.exists(rep_file):
            raise FileNotFoundError(
                f"Repair procedures file not found: {rep_file}\n"
                "Run generate_jsons.py first."
            )

        self._db_conn = sqlite3.connect(db_file, check_same_thread=False)
        self._db_conn.row_factory = sqlite3.Row
        self._db_conn.execute("PRAGMA journal_mode=WAL")

    # ------------------------------------------------------------------
    # recommend_repair
    # ------------------------------------------------------------------

    def recommend_repair(
        self,
        symptom_code: str,
        diagnostic_result: Optional[dict] = None,
        top_k: int = 5,
    ) -> list[dict]:
        """
        Match repairs to a symptom and return ranked recommendations.

        Matching strategy (in priority order)
        --------------------------------------
        1. If ``diagnostic_result`` contains a ``repair_code``, return that
           repair first (exact match from tree traversal).
        2. Match JSON repairs whose ``id`` or ``category`` keywords overlap
           with the symptom_code prefix (e.g. ROF → Roofing).
        3. Keyword-overlap score against repair name + category + materials.
        4. Sort by (score DESC, difficulty ASC) so the easiest effective
           repair is recommended first.

        Parameters
        ----------
        symptom_code      : str   e.g. "PRB-ROF-002"
        diagnostic_result : dict  Optional output from AIDiagnosticEngine.run_diagnostic().
        top_k             : int   Maximum recommendations (default 5).

        Returns
        -------
        list of dicts sorted by descending relevance then ascending difficulty:
        [
          {
            "rank":                  1,
            "id":                    "RP-ROF-001",
            "name":                  "Replacing Asphalt Shingles",
            "category":              "Roofing",
            "difficulty":            "Moderate",
            "difficulty_score":      2,
            "estimated_time":        "2-3 hours",
            "estimated_time_minutes": 150,
            "relevance_score":       0.75,
            "match_reason":          "direct repair_code match",
            "tools_required":        [...],
            "materials_required":    [...],
            "safety_notes":          "...",
            "procedure_steps":       [...],
            "pre_repair_checks":     [...],
            "post_repair_checks":    [...],
            "warnings":              [...],
          },
          ...
        ]
        """
        repairs = self._load_repairs()
        diag    = diagnostic_result or {}

        # ---- extract signals from diagnostic_result ----
        direct_repair_code = diag.get("repair_code")            # e.g. "RP-ROF-001"
        resolution_path    = diag.get("resolution_path") or {}
        recommended_action = diag.get("recommended_action", "")
        tree_category      = diag.get("category", "")

        # derive domain prefix from symptom_code: "PRB-ROF-002" → "ROF"
        parts  = symptom_code.upper().split("-")
        prefix = parts[1] if len(parts) >= 3 else (parts[0] if parts else "")

        # category name from prefix map (same map used in other engines)
        _PREFIX_TO_CAT = {
            "ROF": "Roofing",    "FND": "Foundation",   "PLM": "Plumbing",
            "ELC": "Electrical", "HVC": "HVAC",         "EXT": "Exterior",
            "WIN": "Windows",    "GRG": "Garage",       "SMP": "Basement",
            "APL": "Appliances", "PHN": "Phones",       "TAB": "Tablets",
            "LAP": "Laptops",    "DKT": "Desktops",     "TV":  "TVs",
            "AUD": "Audio",      "CAM": "Cameras",      "NET": "Networking",
            "GAM": "Gaming",     "WRB": "Wearables",    "CAR": "Cars",
            "TRK": "Trucks",     "MCY": "Motorcycles",  "HVY": "Heavy Equipment",
            "HEQ": "Heavy Equipment", "GEN": "Generators", "CMP": "Compressors",
            "PMP": "Pumps",      "MOT": "Motors",       "VAN": "Commercial Vans",
            "SUV": "SUVs",       "EV":  "Electric Vehicles", "SOL": "Solar Systems",
        }
        category_hint = tree_category or _PREFIX_TO_CAT.get(prefix, "")

        # For sym_* codes that don't resolve via prefix, look up the DB
        # to get the symptom name and category for keyword generation
        symptom_name_hint = ""
        if not category_hint and symptom_code.lower().startswith("sym_"):
            try:
                self._require_db()
                row = self._db_conn.execute(
                    "SELECT s.symptom_name, c.category_name "
                    "FROM symptoms s "
                    "LEFT JOIN categories c ON s.category_id = c.category_id "
                    "WHERE s.symptom_code = ?",
                    (symptom_code,)
                ).fetchone()
                if row:
                    category_hint    = row["category_name"] or ""
                    symptom_name_hint = row["symptom_name"] or ""
            except Exception:
                pass

        # keyword bag for fuzzy matching
        query_keywords = self._keywords_for_category(category_hint)

        # Also inject tokens from the symptom name itself for sym_* codes
        if symptom_name_hint:
            extra = set(re.findall(r"[a-z]+", symptom_name_hint.lower()))
            query_keywords = query_keywords | extra

        action_tokens  = set(re.findall(r"[a-z]+", recommended_action.lower()))

        # For sym_* symptom codes, also try direct name-match against repair names
        # by constructing a boosted keyword set from the symptom name tokens
        symptom_name_tokens: set[str] = set()
        if symptom_name_hint:
            symptom_name_tokens = set(
                t for t in re.findall(r"[a-z]+", symptom_name_hint.lower())
                if len(t) > 3
            )

        scored: list[dict] = []
        for rid, rep in repairs.items():
            score, reason = self._score_repair(
                rep, rid,
                direct_repair_code=direct_repair_code,
                category_hint=category_hint,
                query_keywords=query_keywords,
                action_tokens=action_tokens,
                res_path_code=resolution_path.get("repair_code"),
            )
            # Boost score for sym_* codes: check if repair name tokens
            # overlap strongly with the symptom name tokens
            if symptom_name_tokens and score > 0:
                rep_name_tokens = set(
                    t for t in re.findall(r"[a-z]+", rep.get("name", "").lower())
                    if len(t) > 3
                )
                name_overlap = len(symptom_name_tokens & rep_name_tokens)
                if name_overlap >= 2:
                    # Strong name match: boost to near-perfect
                    score = max(score, 0.85)
                    reason = f"symptom name match ({name_overlap} tokens)"
                elif name_overlap == 1:
                    score = max(score, 0.60)
                    reason = f"partial name match"
            if score <= 0:
                continue

            diff_score = _DIFFICULTY_ORDER.get(rep.get("difficulty", "Moderate"), 2)
            scored.append({
                "rank":                   0,
                "id":                     rid,
                "name":                   rep.get("name", ""),
                "category":               rep.get("category", ""),
                "difficulty":             rep.get("difficulty", ""),
                "difficulty_score":       diff_score,
                "estimated_time":         rep.get("estimated_time", ""),
                "estimated_time_minutes": rep.get("estimated_time_minutes", 0),
                "relevance_score":        round(score, 4),
                "match_reason":           reason,
                "tools_required":         rep.get("tools_required", []),
                "materials_required":     rep.get("materials_required", []),
                "safety_notes":           rep.get("safety_notes", ""),
                "procedure_steps":        rep.get("procedure_steps", []),
                "pre_repair_checks":      rep.get("pre_repair_checks", []),
                "post_repair_checks":     rep.get("post_repair_checks", []),
                "warnings":               rep.get("warnings", []),
            })

        # sort: relevance DESC, then difficulty ASC
        scored.sort(key=lambda x: (-x["relevance_score"], x["difficulty_score"]))

        for i, item in enumerate(scored[:top_k]):
            item["rank"] = i + 1

        return scored[:top_k]

    # ------------------------------------------------------------------
    # check_parts_availability
    # ------------------------------------------------------------------

    def check_parts_availability(self, repair_id: str) -> dict:
        """
        Check parts inventory for all materials required by a repair.

        The engine:
          1. Loads the JSON repair to get ``materials_required`` names.
          2. Looks up the SQLite ``repair_procedures`` row by ``repair_code``
             to get the DB-native ``materials_required`` list.
          3. Queries ``parts_inventory`` with fuzzy name matching for each
             material keyword.
          4. Returns stock status, unit cost, total cost estimate, and
             supplier info for every matched part.

        Parameters
        ----------
        repair_id : str   JSON repair key, e.g. "RP-ROF-001"

        Returns
        -------
        dict:
        {
          "repair_id":       "RP-ROF-001",
          "repair_name":     "Replacing Asphalt Shingles",
          "materials_needed": [...],   # from JSON
          "parts": [
            {
              "material_name":  "Matching asphalt shingles",
              "part_id":        1,
              "part_name":      "GAF Timberline HDZ Shingle Bundle",
              "part_code":      "part_roof_shingle",
              "unit":           "bundle",
              "unit_cost":      35.99,
              "current_stock":  500,
              "reorder_level":  100,
              "supplier":       "ABC Supply",
              "lead_time_days": 3,
              "status":         "in_stock",   # in_stock / low_stock / out_of_stock / not_found
              "quantity_needed": 1,
              "line_cost":       35.99,
            },
            ...
          ],
          "total_parts_cost":     35.99,
          "all_parts_available":  True,
          "missing_parts":        [],
          "low_stock_parts":      [],
        }
        """
        self._require_db()
        repairs = self._load_repairs()
        rep     = repairs.get(repair_id)

        if rep is None:
            return {
                "repair_id":           repair_id,
                "repair_name":         None,
                "materials_needed":    [],
                "parts":               [],
                "total_parts_cost":    0.0,
                "all_parts_available": False,
                "missing_parts":       [repair_id],
                "low_stock_parts":     [],
                "error":               f"Repair '{repair_id}' not found in JSON",
            }

        materials: list[str] = rep.get("materials_required", [])
        parts_detail:  list[dict] = []
        total_cost    = 0.0
        missing_parts: list[str] = []
        low_stock:     list[str] = []

        cur = self._db_conn.cursor()

        for material in materials:
            matched = self._find_part_for_material(cur, material)
            if matched:
                row    = matched
                cost   = float(row["average_cost"] or 0)
                stock  = int(row["current_stock"]  or 0)
                reorder = int(row["reorder_level"] or 0)

                if stock == 0:
                    status = "out_of_stock"
                    missing_parts.append(row["part_name"])
                elif stock <= reorder:
                    status = "low_stock"
                    low_stock.append(row["part_name"])
                else:
                    status = "in_stock"

                total_cost += cost
                parts_detail.append({
                    "material_name":   material,
                    "part_id":         row["part_id"],
                    "part_name":       row["part_name"],
                    "part_code":       row["part_code"],
                    "unit":            row["unit"],
                    "unit_cost":       round(cost, 2),
                    "current_stock":   stock,
                    "reorder_level":   reorder,
                    "supplier":        row["supplier"],
                    "supplier_contact": row["supplier_contact"],
                    "lead_time_days":  row["lead_time_days"],
                    "coverage":        row["coverage"],
                    "status":          status,
                    "quantity_needed": 1,
                    "line_cost":       round(cost, 2),
                })
            else:
                missing_parts.append(material)
                parts_detail.append({
                    "material_name":   material,
                    "part_id":         None,
                    "part_name":       None,
                    "part_code":       None,
                    "unit":            None,
                    "unit_cost":       None,
                    "current_stock":   None,
                    "reorder_level":   None,
                    "supplier":        None,
                    "supplier_contact": None,
                    "lead_time_days":  None,
                    "coverage":        None,
                    "status":          "not_found",
                    "quantity_needed": 1,
                    "line_cost":       None,
                })

        return {
            "repair_id":           repair_id,
            "repair_name":         rep.get("name"),
            "materials_needed":    materials,
            "parts":               parts_detail,
            "total_parts_cost":    round(total_cost, 2),
            "all_parts_available": len(missing_parts) == 0,
            "missing_parts":       missing_parts,
            "low_stock_parts":     low_stock,
        }

    # ------------------------------------------------------------------
    # generate_repair_plan
    # ------------------------------------------------------------------

    def generate_repair_plan(
        self,
        symptom_code: str,
        diagnostic_result: Optional[dict] = None,
        top_k: int = 3,
    ) -> dict:
        """
        Generate a complete repair plan: recommendations + parts + cost + time.

        Parameters
        ----------
        symptom_code      : str
        diagnostic_result : dict  Optional AIDiagnosticEngine.run_diagnostic() output.
        top_k             : int   Number of repair options to include (default 3).

        Returns
        -------
        dict:
        {
          "symptom_code":       "PRB-ROF-002",
          "category":           "Roofing",
          "diagnosis_summary":  "...",
          "primary_repair":     { ... full repair dict + parts availability ... },
          "alternative_repairs": [ ... ],
          "total_estimated_time_minutes": 150,
          "total_parts_cost":   35.99,
          "all_parts_available": True,
          "difficulty":         "Moderate",
          "urgency":            "Normal",
          "summary":            "Replace damaged asphalt shingles (Moderate, 2-3 hrs, $35.99 parts)",
          "recommendations":    [ ... top_k repair dicts ... ],
          "plan_steps": [
            "1. Pre-checks: ...",
            "2. Gather tools: ...",
            "3. Step 1: ...",
            ...
            "N. Post-checks: ...",
          ],
        }
        """
        diag = diagnostic_result or {}

        # 1 — get recommendations
        recommendations = self.recommend_repair(symptom_code, diag, top_k=top_k)

        if not recommendations:
            return {
                "symptom_code":                 symptom_code,
                "category":                     diag.get("category", ""),
                "diagnosis_summary":            diag.get("recommended_action", ""),
                "primary_repair":               None,
                "alternative_repairs":          [],
                "total_estimated_time_minutes": 0,
                "total_parts_cost":             0.0,
                "all_parts_available":          False,
                "difficulty":                   "Unknown",
                "urgency":                      "Unknown",
                "summary":                      "No matching repair procedures found.",
                "recommendations":              [],
                "plan_steps":                   [],
            }

        primary = recommendations[0]
        alts    = recommendations[1:]

        # 2 — check parts for primary repair
        parts_info = self.check_parts_availability(primary["id"])

        # 3 — merge parts into primary
        primary_with_parts = {**primary, "parts_availability": parts_info}

        # 4 — calculate totals
        total_time  = primary["estimated_time_minutes"] or 0
        total_cost  = parts_info["total_parts_cost"]
        all_avail   = parts_info["all_parts_available"]

        # 5 — urgency from severity (if passed through diagnostic_result)
        severity_map = {
            "Critical": "Immediate",
            "High":     "Urgent",
            "Medium":   "Normal",
            "Low":      "Routine",
            "Variable": "Normal",
        }
        raw_severity = diag.get("severity", "")
        urgency      = severity_map.get(raw_severity, "Normal")

        # 6 — assemble ordered plan steps
        plan_steps = self._build_plan_steps(primary)

        # 7 — one-line summary
        time_label = primary["estimated_time"] or f"{total_time} min"
        cost_label = f"${total_cost:.2f} parts" if total_cost else "see parts list"
        summary = (
            f"{primary['name']} "
            f"({primary['difficulty']}, {time_label}, {cost_label})"
        )

        return {
            "symptom_code":                 symptom_code,
            "category":                     diag.get("category", primary.get("category", "")),
            "diagnosis_summary":            diag.get("recommended_action", ""),
            "primary_repair":               primary_with_parts,
            "alternative_repairs":          alts,
            "total_estimated_time_minutes": total_time,
            "total_parts_cost":             total_cost,
            "all_parts_available":          all_avail,
            "difficulty":                   primary["difficulty"],
            "urgency":                      urgency,
            "summary":                      summary,
            "recommendations":              recommendations,
            "plan_steps":                   plan_steps,
        }

    # ------------------------------------------------------------------
    # close / context manager
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release the SQLite connection."""
        if self._db_conn:
            self._db_conn.close()
            self._db_conn = None

    def __enter__(self) -> "AIRepairReasoningEngine":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        label   = self._cfg.get("label", f"v{self.version}")
        nrepairs = len(self._repairs_cache) if self._repairs_cache else "?"
        return (
            f"AIRepairReasoningEngine(version={self.version}, "
            f"label={label!r}, repairs_loaded={nrepairs})"
        )

    # ==================================================================
    # Private helpers
    # ==================================================================

    # --- JSON loading ---

    def _load_repairs(self) -> dict:
        """Load and cache repair_procedures.json."""
        if self._repairs_cache is not None:
            return self._repairs_cache
        path = os.path.join(self._cfg["json_dir"], "repair_procedures.json")
        with open(path, "r", encoding="utf-8") as f:
            self._repairs_cache = json.load(f)
        return self._repairs_cache

    # --- scoring ---

    def _score_repair(
        self,
        rep:               dict,
        rid:               str,
        direct_repair_code: Optional[str],
        category_hint:     str,
        query_keywords:    set[str],
        action_tokens:     set[str],
        res_path_code:     Optional[str],
    ) -> tuple[float, str]:
        """
        Return (score, reason) for one repair entry.

        Score tiers
        -----------
        1.00  direct repair_code match from diagnostic result
        0.90  resolution_path repair_code match
        0.70  category exact match
        0.40–0.69  keyword overlap with name / category / materials
        0.00  no match
        """
        # Tier 1 — direct code match
        if direct_repair_code and rid == direct_repair_code:
            return 1.00, "direct repair_code match"

        # Tier 2 — resolution path repair_code match
        if res_path_code and rid == res_path_code:
            return 0.90, "resolution path repair_code match"

        rep_category = rep.get("category", "")

        # Tier 3 — category match
        if category_hint and rep_category.lower() == category_hint.lower():
            # Add action token overlap bonus
            name_tokens = set(re.findall(r"[a-z]+", rep.get("name", "").lower()))
            bonus = 0.10 * (len(action_tokens & name_tokens) / max(len(action_tokens), 1))
            return round(0.70 + bonus, 4), "category match"

        # Tier 4 — keyword overlap
        if not query_keywords:
            return 0.0, ""

        target_text = " ".join([
            rep.get("name", ""),
            rep_category,
            " ".join(rep.get("materials_required", [])),
            rep.get("safety_notes", ""),
        ]).lower()
        target_tokens = set(re.findall(r"[a-z]+", target_text))
        overlap       = len(query_keywords & target_tokens)

        if overlap == 0:
            return 0.0, ""

        score = round(0.40 + 0.29 * (overlap / max(len(query_keywords), 1)), 4)
        return score, f"keyword overlap ({overlap} tokens)"

    @staticmethod
    def _keywords_for_category(category: str) -> set[str]:
        """Return the keyword set for a category, falling back to empty set."""
        kws = _CATEGORY_KEYWORDS.get(category, [])
        return set(kws)

    # --- parts matching ---

    def _find_part_for_material(
        self, cur: sqlite3.Cursor, material: str
    ) -> Optional[sqlite3.Row]:
        """
        Find the best matching parts_inventory row for a material description.

        Strategy:
          1. Exact part_name match (case-insensitive).
          2. Each significant word in the material name searched via LIKE.
          3. Return the row with highest current_stock among candidates.
        """
        # strip generic filler words
        _FILLER = {"replacement", "or", "if", "and", "with", "a", "an", "the",
                   "model", "specific", "use", "high", "quality", "grade",
                   "certified", "equivalent", "optional"}

        mat_lc    = material.lower()
        mat_words = [
            w for w in re.findall(r"[a-z0-9]+", mat_lc)
            if w not in _FILLER and len(w) > 2
        ]

        # 1 — exact name match
        row = cur.execute(
            "SELECT * FROM parts_inventory "
            "WHERE LOWER(part_name) = ? "
            "ORDER BY current_stock DESC LIMIT 1",
            (mat_lc,),
        ).fetchone()
        if row:
            return row

        # 2 — each keyword as LIKE search; collect all candidates
        candidates: list[sqlite3.Row] = []
        for word in mat_words[:4]:          # cap at 4 keywords
            rows = cur.execute(
                "SELECT * FROM parts_inventory "
                "WHERE LOWER(part_name) LIKE ? "
                "ORDER BY current_stock DESC LIMIT 5",
                (f"%{word}%",),
            ).fetchall()
            candidates.extend(rows)

        if not candidates:
            return None

        # rank by how many material words appear in the part name
        def _rank(r: sqlite3.Row) -> int:
            pn = r["part_name"].lower()
            return sum(1 for w in mat_words if w in pn)

        candidates.sort(key=_rank, reverse=True)
        return candidates[0]

    # --- plan steps ---

    @staticmethod
    def _build_plan_steps(repair: dict) -> list[str]:
        """
        Assemble a numbered, human-readable ordered plan from a repair dict.

        Order: pre_repair_checks → tools list → procedure_steps → post_repair_checks
        """
        steps: list[str] = []
        n = 1

        pre = repair.get("pre_repair_checks", [])
        if pre:
            steps.append(f"{n}. [Pre-checks]")
            n += 1
            for item in pre:
                steps.append(f"   • {item}")

        tools = repair.get("tools_required", [])
        if tools:
            steps.append(f"{n}. [Gather tools]  {', '.join(tools[:6])}"
                         + (" …" if len(tools) > 6 else ""))
            n += 1

        for s in repair.get("procedure_steps", []):
            title  = s.get("title", f"Step {s.get('step', n)}")
            detail = s.get("detail", s.get("action", ""))
            steps.append(f"{n}. {title}")
            if detail:
                # wrap long detail at ~100 chars
                steps.append(f"   {detail[:200]}" + ("…" if len(detail) > 200 else ""))
            n += 1

        post = repair.get("post_repair_checks", [])
        if post:
            steps.append(f"{n}. [Post-checks]")
            n += 1
            for item in post:
                steps.append(f"   • {item}")

        warn = repair.get("warnings", [])
        if warn:
            steps.append(f"{n}. [Warnings]")
            for w in warn:
                steps.append(f"   ⚠  {w}")

        return steps

    # --- misc ---

    def _require_db(self) -> None:
        if self._db_conn is None:
            raise RuntimeError(
                "SQLite connection is closed. "
                "Create a new AIRepairReasoningEngine instance."
            )

    @staticmethod
    def _parse_json(value: Any) -> Any:
        if value is None:
            return []
        if isinstance(value, (list, dict)):
            return value
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
