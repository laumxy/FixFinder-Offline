from __future__ import annotations

import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any


class DiagnosticLookup:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else Path(__file__).resolve().parent / "diagnostics" / "diagnostic_trees.sqlite3"

    def exists(self) -> bool:
        return self.db_path.exists()

    def get_questions_for_repair(self, repair_id: str) -> List[Dict[str, Any]]:
        if not self.exists():
            return []
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT tree_id, question, possible_answers, next_action FROM diagnostic_tree WHERE repair_id = ?",
            (repair_id,)
        )
        rows = cur.fetchall()
        conn.close()
        out: List[Dict[str, Any]] = []
        for tree_id, question, possible_answers, next_action in rows:
            try:
                possible = json.loads(possible_answers)
            except Exception:
                possible = []
            try:
                next_a = json.loads(next_action)
            except Exception:
                next_a = {}
            out.append({"tree_id": tree_id, "question": question, "possible_answers": possible, "next_action": next_a})
        return out
