"""
ai_engine/diagnostic_engine.py
================================
FixFinder AI Diagnostic Engine.

Combines:
  • Tokenised keyword scoring against the SQLite symptoms table for
    symptom matching (no ML dependency required).
  • JSON diagnostic tree loading from Version_X/05_JSON/
  • Step-by-step tree traversal driven by yes/no user responses.

Usage
-----
    from ai_engine.diagnostic_engine import AIDiagnosticEngine

    with AIDiagnosticEngine(version=1) as eng:
        # 1 – find the most likely symptoms from plain text
        matches = eng.analyze_symptoms("roof leaking near chimney after rain")

        # 2 – load the full diagnostic tree for the top match
        tree = eng.get_diagnostic_tree(matches[0]["symptom_code"])

        # 3 – walk the tree with collected yes/no answers
        result = eng.run_diagnostic(
            matches[0]["symptom_code"],
            user_responses=["yes", "no", "yes"]
        )
        print(result["recommended_action"])
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
        "label":      "Home Maintenance",
        "db_path":    os.path.join(_ROOT, "Version_1", "03_SQLite_Database", "fixfinder_v1.db"),
        "json_dir":   os.path.join(_ROOT, "Version_1", "05_JSON"),
    },
    2: {
        "label":      "Electronics",
        "db_path":    os.path.join(_ROOT, "Version_2", "03_SQLite_Database", "fixfinder_v2.db"),
        "json_dir":   os.path.join(_ROOT, "Version_2", "05_JSON"),
    },
    3: {
        "label":      "Industrial / Automotive",
        "db_path":    os.path.join(_ROOT, "Version_3", "03_SQLite_Database", "fixfinder_v3.db"),
        "json_dir":   os.path.join(_ROOT, "Version_3", "05_JSON"),
    },
}

# Common English stop-words excluded from scoring
_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "is", "it", "in", "on", "at", "to", "of", "for",
    "and", "or", "but", "not", "no", "yes", "with", "from", "by", "are",
    "was", "be", "been", "has", "have", "had", "do", "does", "did",
    "my", "my", "i", "me", "we", "us", "you", "he", "she", "they",
    "this", "that", "its", "after", "before", "when", "how", "what",
    "can", "will", "would", "could", "should", "may", "might", "must",
    "very", "just", "also", "more", "some", "any", "all",
})


# ===========================================================================
# AIDiagnosticEngine
# ===========================================================================

class AIDiagnosticEngine:
    """
    Step-by-step diagnostic engine for a single FixFinder version.

    Lifecycle
    ---------
    1. ``AIDiagnosticEngine(version=1|2|3)`` — loads DB + JSON trees.
    2. ``analyze_symptoms(text)`` — score-rank symptoms against user text.
    3. ``get_diagnostic_tree(symptom_code)`` — return the matching tree dict.
    4. ``run_diagnostic(symptom_code, user_responses)`` — traverse the tree.
    5. ``close()`` — release SQLite connection.

    Use as a context manager for automatic cleanup.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, version: int) -> None:
        if version not in _VERSION_CONFIG:
            raise ValueError(f"version must be 1, 2, or 3 — got {version!r}")

        self.version = version
        self._cfg    = _VERSION_CONFIG[version]

        self._db_conn:     Optional[sqlite3.Connection] = None
        self._trees_cache: Optional[dict]               = None   # lazy

        # Load eagerly so errors surface at construction time
        self.load_version(self._cfg)

    # ------------------------------------------------------------------
    # load_version
    # ------------------------------------------------------------------

    def load_version(self, version_path: dict) -> None:
        """
        Open the SQLite connection and validate the JSON tree file exists.

        Parameters
        ----------
        version_path : dict
            Entry from ``_VERSION_CONFIG``, with keys ``db_path`` and
            ``json_dir``.
        """
        db_file   = version_path["db_path"]
        json_dir  = version_path["json_dir"]
        tree_file = os.path.join(json_dir, "diagnostic_trees.json")

        if not os.path.exists(db_file):
            raise FileNotFoundError(f"SQLite database not found: {db_file}")
        if not os.path.exists(tree_file):
            raise FileNotFoundError(
                f"Diagnostic trees file not found: {tree_file}\n"
                "Run generate_jsons.py first."
            )

        self._db_conn = sqlite3.connect(db_file, check_same_thread=False)
        self._db_conn.row_factory = sqlite3.Row
        self._db_conn.execute("PRAGMA journal_mode=WAL")

    # ------------------------------------------------------------------
    # analyze_symptoms
    # ------------------------------------------------------------------

    def analyze_symptoms(self, user_input: str, top_k: int = 5) -> list[dict]:
        """
        Match free-text user input against the symptoms table.

        Scoring algorithm
        -----------------
        For every symptom row we build a *target corpus* from:
          - symptom_name  (weight ×3 — most important signal)
          - description   (weight ×2)
          - common_causes (weight ×1)

        We tokenise both the query and the corpus, remove stop-words, then
        compute a weighted token-overlap score normalised to [0, 1]:

            score = weighted_matches / (total_query_tokens × max_weight)

        An exact sub-string bonus (+0.2) is added when the full query
        appears verbatim (case-insensitive) inside the symptom name.

        Parameters
        ----------
        user_input : str   Natural-language description of the problem.
        top_k      : int   Maximum matches to return (default 5).

        Returns
        -------
        list of dicts, sorted by descending score:
        [
          {
            "rank":         1,
            "symptom_id":   42,
            "symptom_code": "PRB-ROF-002",
            "symptom_name": "Roof Leak",
            "severity":     "High",
            "description":  "Water intrusion through roof...",
            "causes":       ["Damaged flashing", "cracked shingles"],
            "score":        0.4286,
            "matched_tokens": ["leak", "roof", "chimney"],
          },
          ...
        ]
        """
        self._require_db()

        query_tokens = self._tokenize(user_input)
        if not query_tokens:
            return []

        cur = self._db_conn.cursor()
        rows = cur.execute(
            "SELECT symptom_id, symptom_name, symptom_code, severity, "
            "description, common_causes "
            "FROM symptoms"
        ).fetchall()

        scored: list[dict] = []
        for row in rows:
            score, matched = self._score_symptom(row, query_tokens, user_input)
            if score > 0:
                causes = self._parse_json(row["common_causes"])
                scored.append({
                    "rank":           0,       # filled below
                    "symptom_id":     row["symptom_id"],
                    "symptom_code":   row["symptom_code"],
                    "symptom_name":   row["symptom_name"],
                    "severity":       row["severity"],
                    "description":    row["description"],
                    "causes":         causes,
                    "score":          round(score, 4),
                    "matched_tokens": matched,
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        top = scored[:top_k]
        for i, item in enumerate(top):
            item["rank"] = i + 1

        return top

    # ------------------------------------------------------------------
    # get_diagnostic_tree
    # ------------------------------------------------------------------

    def get_diagnostic_tree(self, symptom_code: str) -> Optional[dict]:
        """
        Find and return the diagnostic tree whose ``symptom_code`` matches.

        The trees JSON is keyed by tree-ID (e.g. ``DT-ROF-001``); we search
        by the ``symptom_code`` field inside each tree.

        Parameters
        ----------
        symptom_code : str   e.g. "PRB-ROF-002"

        Returns
        -------
        Full tree dict (id, name, category, steps, decision_points,
        resolution_paths, …) or ``None`` if not found.
        """
        trees = self._load_trees()

        # Primary: match by symptom_code field
        for tree in trees.values():
            if tree.get("symptom_code") == symptom_code:
                return tree

        # Fallback: match by tree ID directly (caller may pass DT-xxx)
        if symptom_code in trees:
            return trees[symptom_code]

        # Soft fallback: partial case-insensitive match on tree name
        norm = symptom_code.lower()
        for tree in trees.values():
            if norm in tree.get("name", "").lower():
                return tree

        return None

    # ------------------------------------------------------------------
    # run_diagnostic
    # ------------------------------------------------------------------

    def run_diagnostic(
        self,
        symptom_code: str,
        user_responses: list[str],
    ) -> dict:
        """
        Traverse a diagnostic tree using collected yes/no answers.

        Parameters
        ----------
        symptom_code   : str        Symptom code or tree ID to diagnose.
        user_responses : list[str]  Ordered answers — each element should
                                    be "yes" / "y" / "1" / True for YES,
                                    anything else is treated as NO.

        The traversal follows ``decision_points`` in order.  Each
        decision-point's ``yes`` / ``no`` value is either:
          • a ``repair_code``-style string (e.g. "RP-ROF-001") → terminal,
          • a free-text next-step description → non-terminal (continue),
          • None / empty → continue to next decision point.

        Returns
        -------
        dict with keys:
          "tree_id"            – str
          "tree_name"          – str
          "symptom_code"       – str
          "steps_presented"    – list of step dicts traversed
          "decisions_made"     – list of {"question", "answer", "outcome"}
          "recommended_action" – str   human-readable final recommendation
          "repair_code"        – str | None
          "resolution_path"    – dict | None  matching resolution_paths entry
          "diagnosis_complete" – bool
          "remaining_steps"    – int   how many more steps would remain
        """
        tree = self.get_diagnostic_tree(symptom_code)
        if tree is None:
            return {
                "tree_id":            None,
                "tree_name":          None,
                "symptom_code":       symptom_code,
                "steps_presented":    [],
                "decisions_made":     [],
                "recommended_action": f"No diagnostic tree found for symptom code: {symptom_code}",
                "repair_code":        None,
                "resolution_path":    None,
                "diagnosis_complete": False,
                "remaining_steps":    0,
            }

        steps      = tree.get("steps", [])
        dps        = tree.get("decision_points", [])
        res_paths  = tree.get("resolution_paths", [])

        steps_presented: list[dict]  = []
        decisions_made:  list[dict]  = []
        repair_code:     Optional[str] = None
        final_action:    str         = ""
        complete:        bool        = False

        # Walk through decision points, consuming one user_response each
        for idx, dp in enumerate(dps):
            # Present the corresponding step (1-indexed, may not align exactly)
            if idx < len(steps):
                steps_presented.append(steps[idx])

            # Consume the answer for this decision point
            raw_answer = user_responses[idx] if idx < len(user_responses) else None
            answered   = self._is_yes(raw_answer)
            answer_str = "yes" if answered else "no"

            outcome = dp["yes"] if answered else dp["no"]

            decisions_made.append({
                "dp_id":    dp.get("id", f"DP-{idx+1}"),
                "question": dp.get("question", ""),
                "answer":   answer_str,
                "outcome":  outcome,
            })

            # Check if this outcome is terminal (contains a repair code pattern)
            detected_code = self._extract_repair_code(outcome)
            if detected_code:
                repair_code  = detected_code
                final_action = outcome
                complete     = True
                break

            # If outcome is a non-trivial resolution directive (not just
            # "continue" phrasing) treat it as terminal guidance
            if self._is_terminal_outcome(outcome):
                final_action = outcome
                complete     = True
                break

        # If we ran out of responses before completing, report where we stopped
        remaining = max(0, len(dps) - len(decisions_made))

        # If we never hit a terminal, surface the last outcome as guidance
        if not final_action and decisions_made:
            final_action = decisions_made[-1]["outcome"]

        if not final_action:
            final_action = "Unable to determine — provide more information."

        # Find the best matching resolution path
        resolution_path = self._match_resolution_path(res_paths, repair_code, final_action)

        return {
            "tree_id":            tree["id"],
            "tree_name":          tree["name"],
            "symptom_code":       tree.get("symptom_code", symptom_code),
            "category":           tree.get("category", ""),
            "steps_presented":    steps_presented,
            "decisions_made":     decisions_made,
            "recommended_action": final_action,
            "repair_code":        repair_code,
            "resolution_path":    resolution_path,
            "diagnosis_complete": complete,
            "remaining_steps":    remaining,
            "avg_resolution_time_minutes": tree.get("avg_resolution_time_minutes"),
            "success_rate_percentage":     tree.get("success_rate_percentage"),
        }

    # ------------------------------------------------------------------
    # close / context manager
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release the SQLite connection."""
        if self._db_conn:
            self._db_conn.close()
            self._db_conn = None

    def __enter__(self) -> "AIDiagnosticEngine":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        label  = self._cfg.get("label", f"v{self.version}")
        ntrees = len(self._trees_cache) if self._trees_cache else "?"
        return (
            f"AIDiagnosticEngine(version={self.version}, "
            f"label={label!r}, trees_loaded={ntrees})"
        )

    # ==================================================================
    # Private helpers
    # ==================================================================

    # --- tokenization / scoring ---

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """
        Lower-case, strip punctuation, split on whitespace, remove stop-words.
        Returns a list of meaningful tokens.
        """
        text   = text.lower()
        tokens = re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text)
        return [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]

    def _score_symptom(
        self,
        row: sqlite3.Row,
        query_tokens: list[str],
        raw_query: str,
    ) -> tuple[float, list[str]]:
        """
        Compute a weighted token-overlap score for one symptom row.

        Returns (score_float, matched_token_list).
        """
        name_tokens   = self._tokenize(row["symptom_name"]   or "")
        desc_tokens   = self._tokenize(row["description"]    or "")
        cause_raw     = row["common_causes"] or ""
        # common_causes may be a JSON list string
        try:
            causes_list = json.loads(cause_raw)
            cause_text  = " ".join(causes_list) if isinstance(causes_list, list) else cause_raw
        except (json.JSONDecodeError, TypeError):
            cause_text  = cause_raw
        cause_tokens  = self._tokenize(cause_text)

        # Build weighted token bag: {token: max_weight_seen}
        weighted: dict[str, int] = {}
        for t in name_tokens:
            weighted[t] = max(weighted.get(t, 0), 3)
        for t in desc_tokens:
            weighted[t] = max(weighted.get(t, 0), 2)
        for t in cause_tokens:
            weighted[t] = max(weighted.get(t, 0), 1)

        if not weighted:
            return 0.0, []

        matched_tokens: list[str] = []
        weighted_score = 0
        for qt in set(query_tokens):      # deduplicate query tokens
            if qt in weighted:
                weighted_score += weighted[qt]
                matched_tokens.append(qt)

        if weighted_score == 0:
            return 0.0, []

        max_possible = len(set(query_tokens)) * 3   # all tokens matched at weight 3
        score        = weighted_score / max_possible

        # Exact sub-string bonus
        symptom_name_lc = (row["symptom_name"] or "").lower()
        raw_lc          = raw_query.lower().strip()
        if len(raw_lc) > 3 and raw_lc in symptom_name_lc:
            score = min(1.0, score + 0.20)

        return score, matched_tokens

    # --- tree loading ---

    def _load_trees(self) -> dict:
        """Load and cache diagnostic_trees.json for this version."""
        if self._trees_cache is not None:
            return self._trees_cache

        tree_file = os.path.join(self._cfg["json_dir"], "diagnostic_trees.json")
        with open(tree_file, "r", encoding="utf-8") as f:
            self._trees_cache = json.load(f)
        return self._trees_cache

    # --- traversal helpers ---

    @staticmethod
    def _is_yes(answer: Any) -> bool:
        """Return True if answer represents an affirmative."""
        if answer is None:
            return False
        if isinstance(answer, bool):
            return answer
        return str(answer).strip().lower() in {"yes", "y", "1", "true", "t"}

    _REPAIR_CODE_RE = re.compile(r"\bRP-[A-Z]{2,6}-\d{3}\b")

    @classmethod
    def _extract_repair_code(cls, text: str) -> Optional[str]:
        """Return the first RP-XXX-NNN code found in text, or None."""
        if not text:
            return None
        m = cls._REPAIR_CODE_RE.search(text)
        return m.group(0) if m else None

    # Phrases that indicate a definitive (terminal) diagnostic outcome
    _TERMINAL_PHRASES: tuple[str, ...] = (
        "professional service",
        "call technician",
        "contact manufacturer",
        "replace internal display",
        "motherboard",
        "logic board",
        "do not drive",
        "engage licensed",
        "service needed",
        "dealer scan",
        "installer",
    )

    @classmethod
    def _is_terminal_outcome(cls, outcome: str) -> bool:
        """Return True if outcome text indicates a definitive end-state."""
        if not outcome:
            return False
        lo = outcome.lower()
        return any(phrase in lo for phrase in cls._TERMINAL_PHRASES)

    @staticmethod
    def _match_resolution_path(
        res_paths: list[dict],
        repair_code: Optional[str],
        final_action: str,
    ) -> Optional[dict]:
        """
        Find the resolution path that best matches the outcome.

        Priority:
          1. Exact repair_code match.
          2. action text contains a word from final_action.
          3. First path whose condition overlaps final_action.
        """
        if not res_paths:
            return None

        # 1 — exact repair code
        if repair_code:
            for p in res_paths:
                if p.get("repair_code") == repair_code:
                    return p

        # 2 — action keyword overlap
        fa_words = set(re.findall(r"[a-z]+", final_action.lower()))
        best_path   = None
        best_overlap = 0
        for p in res_paths:
            action_words = set(re.findall(r"[a-z]+", p.get("action", "").lower()))
            overlap      = len(fa_words & action_words)
            if overlap > best_overlap:
                best_overlap = overlap
                best_path    = p

        if best_path:
            return best_path

        # 3 — condition keyword overlap
        for p in res_paths:
            cond_words = set(re.findall(r"[a-z]+", p.get("condition", "").lower()))
            if fa_words & cond_words:
                return p

        return res_paths[0]   # last resort: return first path

    # --- misc ---

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

    def _require_db(self) -> None:
        if self._db_conn is None:
            raise RuntimeError(
                "SQLite connection is closed. "
                "Create a new AIDiagnosticEngine instance."
            )
