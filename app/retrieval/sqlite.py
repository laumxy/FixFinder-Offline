import json
import re
import sqlite3
from pathlib import Path
from typing import Any


class KnowledgeRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        # Persistent connection — opened once, reused for every call.
        # check_same_thread=False is safe here because FastAPI runs handlers
        # in the same thread (sync routes) and we never share this object
        # across threads without the pipeline singleton pattern.
        self._conn: sqlite3.Connection | None = None

    # ── Connection management ─────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        """Return the persistent connection, creating it if needed."""
        if self._conn is None:
            if not self.db_path.exists():
                raise FileNotFoundError(f"Database not found: {self.db_path}")
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # Write-ahead log keeps reads fast under concurrent access
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._conn = conn
        return self._conn

    def _safe_connect(self) -> sqlite3.Connection | None:
        """Return connection or None if the DB file doesn't exist yet."""
        if not self.db_path.exists():
            return None
        return self._connect()

    # ── Public API ────────────────────────────────────────────────────────────

    def get_problem(self, problem_id: int) -> dict[str, Any] | None:
        conn = self._safe_connect()
        if conn is None:
            return None
        row = conn.execute(
            "SELECT * FROM problems WHERE id = ?",
            (problem_id,),
        ).fetchone()
        return self._row_to_problem(row) if row else None

    def get_problems_by_ids(self, ids: list[int]) -> dict[int, dict[str, Any]]:
        """
        Batch-fetch multiple problems in a single query.
        Returns a dict keyed by problem id.
        Replaces the N+1 get_problem() loop in merge_matches().
        """
        if not ids:
            return {}
        conn = self._safe_connect()
        if conn is None:
            return {}
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT * FROM problems WHERE id IN ({placeholders})",
            ids,
        ).fetchall()
        return {row["id"]: self._row_to_problem(row) for row in rows}

    def search_problems(self, query: str, category: str | None, limit: int = 5) -> list[dict[str, Any]]:
        conn = self._safe_connect()
        if conn is None:
            return []

        terms = [term for term in query.split() if len(term) > 2]

        # 1. Try FTS with category filter
        rows = self._fts_rows(conn, terms, category, limit)

        # 2. If no results and category is specific, retry FTS without category filter
        if not rows and category and category != "general":
            rows = self._fts_rows(conn, terms, None, limit)

        # 3. Broad LIKE-based fallback
        if not rows and terms:
            rows = self._like_search(conn, terms, limit)

        results = []
        for row in rows:
            problem = self._row_to_problem(row)
            haystack_tokens = self._tokens(problem.get("search_text") or self._search_text(problem))
            lexical_score = sum(1 for term in terms if term in haystack_tokens)

            title_tokens = self._tokens(problem["problem"])
            title_match = sum(2 for term in terms if term in title_tokens)
            lexical_score += title_match

            symptom_tokens = self._tokens(" ".join(problem.get("symptoms", [])))
            symptom_match = sum(1 for term in terms if term in symptom_tokens)
            lexical_score += symptom_match

            category_bonus = 3 if category and category != "general" and problem["category"] == category else 0
            fts_bonus = float(problem.pop("_fts_score", 0.0))
            score = lexical_score + category_bonus + fts_bonus
            if score > 0:
                problem["retrieval_score"] = float(score)
                problem["retrieval_source"] = "sqlite"
                results.append(problem)

        return sorted(results, key=lambda item: item["retrieval_score"], reverse=True)[:limit]

    def merge_matches(
        self,
        keyword_matches: list[dict[str, Any]],
        vector_matches: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged: dict[int, dict[str, Any]] = {}

        for match in keyword_matches:
            merged[match["id"]] = match

        # Collect all vector-match IDs that are NOT already in merged, then
        # fetch them all in one query instead of one query per ID.
        missing_ids = [
            int(vm["id"]) for vm in vector_matches if int(vm["id"]) not in merged
        ]
        fetched = self.get_problems_by_ids(missing_ids)

        for vector_match in vector_matches:
            pid = int(vector_match["id"])
            problem = merged.get(pid) or fetched.get(pid)
            if not problem:
                continue
            existing = merged.get(problem["id"], problem)
            existing["retrieval_score"] = max(
                float(existing.get("retrieval_score", 0.0)),
                float(vector_match.get("score", 0.0)) * 10.0,
            )
            existing["semantic_score"] = float(vector_match.get("score", 0.0))
            existing["retrieval_source"] = "sqlite+faiss" if problem["id"] in merged else "faiss"
            merged[problem["id"]] = existing

        return sorted(merged.values(), key=lambda item: item.get("retrieval_score", 0.0), reverse=True)

    def count_problems(self) -> int:
        conn = self._safe_connect()
        if conn is None:
            return 0
        row = conn.execute("SELECT COUNT(*) AS total FROM problems").fetchone()
        return int(row["total"])

    # ── Private helpers ───────────────────────────────────────────────────────

    def _like_search(
        self,
        connection: sqlite3.Connection,
        terms: list[str],
        limit: int,
    ) -> list[sqlite3.Row]:
        """Fallback: search problems using LIKE on problem title + symptoms."""
        clauses = []
        params: list[Any] = []
        for term in terms:
            clauses.append("(p.problem LIKE ? OR p.symptoms LIKE ? OR p.causes LIKE ? OR p.repair_steps LIKE ?)")
            like_pattern = f"%{term}%"
            params.extend([like_pattern, like_pattern, like_pattern, like_pattern])
        where = " OR ".join(clauses)
        params.append(limit)
        try:
            return connection.execute(
                f"SELECT p.*, 0.5 AS _fts_score FROM problems p WHERE {where} LIMIT ?",
                params,
            ).fetchall()
        except sqlite3.OperationalError:
            return []

    def _fts_rows(
        self,
        connection: sqlite3.Connection,
        terms: list[str],
        category: str | None,
        limit: int,
    ) -> list[sqlite3.Row]:
        if not terms:
            return []

        fts_query = " OR ".join(f'"{term}"' for term in terms)
        params: list[Any] = [fts_query]
        category_filter = ""
        if category and category != "general":
            category_filter = "AND p.category = ?"
            params.append(category)
        params.append(limit)

        try:
            return connection.execute(
                f"""
                SELECT p.*, 2.0 AS _fts_score
                FROM problem_search ps
                JOIN problems p ON p.id = ps.rowid
                WHERE problem_search MATCH ?
                {category_filter}
                ORDER BY bm25(problem_search)
                LIMIT ?
                """,
                params,
            ).fetchall()
        except sqlite3.OperationalError:
            return []

    @staticmethod
    def _row_to_problem(row: sqlite3.Row) -> dict[str, Any]:
        keys = row.keys()
        return {
            "id": row["id"],
            "category": row["category"],
            "problem": row["problem"],
            "aliases": json.loads(row["aliases"]) if "aliases" in keys else [],
            "symptoms": json.loads(row["symptoms"]),
            "causes": json.loads(row["causes"]),
            "inspection_steps": json.loads(row["inspection_steps"]),
            "repair_steps": json.loads(row["repair_steps"]),
            "tools": json.loads(row["tools"]),
            "safety": json.loads(row["safety"]),
            "prevention": json.loads(row["prevention"]),
            "difficulty": row["difficulty"] if "difficulty" in keys else "moderate",
            "risk_level": row["risk_level"] if "risk_level" in keys else "medium",
            "estimated_time": row["estimated_time"] if "estimated_time" in keys else "unknown",
            "source_type": row["source_type"] if "source_type" in keys else "seed",
            "source_url": row["source_url"] if "source_url" in keys else "",
            "reliability_score": row["reliability_score"] if "reliability_score" in keys else 1.0,
            "confidence_score": row["confidence_score"] if "confidence_score" in keys else 1.0,
            "knowledge_version": row["knowledge_version"] if "knowledge_version" in keys else "v1.0",
            "search_text": row["search_text"] if "search_text" in keys else "",
            "_fts_score": row["_fts_score"] if "_fts_score" in keys else 0.0,
        }

    @staticmethod
    def _search_text(problem: dict[str, Any]) -> str:
        return " ".join(
            [
                problem["problem"],
                problem["category"],
                " ".join(problem.get("aliases", [])),
                " ".join(problem["symptoms"]),
                " ".join(problem["causes"]),
                " ".join(problem["inspection_steps"]),
                " ".join(problem["repair_steps"]),
                " ".join(problem["tools"]),
                " ".join(problem["safety"]),
                " ".join(problem["prevention"]),
            ]
        ).lower()

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return set(re.findall(r"[a-z0-9-]+", text.lower()))
