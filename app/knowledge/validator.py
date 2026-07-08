from __future__ import annotations

import sqlite3
import json
from datetime import datetime, timezone
from typing import Any

from app.database.models import KnowledgeProblem
from app.knowledge.cleaner import KnowledgeCleaner
from app.database.db import fetch_all_problem_records, get_connection
from fixfinder_engine.config import settings


class ValidationEngine:
    """Validate KnowledgeProblem records before they enter production.

    Checks performed:
    - required fields present
    - duplicate detection (category + problem)
    - conflicting repairs (existing record with different repair steps)
    - unsafe instructions (uses KnowledgeCleaner unsafe patterns)
    - missing safety warnings
    - invalid categories
    - basic relationship checks (inspection vs repair steps)
    """

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or settings.database_path
        self.cleaner = KnowledgeCleaner()
        # build a category whitelist from existing DB records
        try:
            records = fetch_all_problem_records(self.db_path)
            self._category_whitelist = {r["category"] for r in records}
        except Exception:
            self._category_whitelist = set()

    def validate(self, problem: KnowledgeProblem, connection: sqlite3.Connection | None = None) -> dict[str, Any]:
        issues: list[str] = []

        # Required fields
        required = [
            ("category", problem.category),
            ("problem", problem.problem),
            ("symptoms", problem.symptoms),
            ("causes", problem.causes),
            ("inspection_steps", problem.inspection_steps),
            ("repair_steps", problem.repair_steps),
            ("tools", problem.tools),
            ("safety", problem.safety),
        ]
        for name, value in required:
            if not value:
                issues.append(f"missing_{name}")

        # Basic category check
        if not isinstance(problem.category, str) or len(problem.category.strip()) < 2:
            issues.append("invalid_category")
        else:
            if self._category_whitelist and problem.category not in self._category_whitelist:
                issues.append("category_not_in_whitelist")

        # Unsafe instructions check (expanded): reuse cleaner and also flag hazardous verbs
        combined_instructions = "\n".join(problem.repair_steps or []) + "\n" + "\n".join(problem.inspection_steps or [])
        if not self.cleaner.is_safe(combined_instructions):
            issues.append("unsafe_instructions")
        # Look for explicit hazardous imperative patterns
        hazardous_terms = ["bypass", "short", "remove safety", "do not wear", "cut live"]
        lowered = combined_instructions.lower()
        for term in hazardous_terms:
            if term in lowered:
                issues.append(f"hazardous_term:{term}")

        # Missing safety warnings
        if not problem.safety or all(not s.strip() for s in problem.safety):
            issues.append("missing_safety_warnings")

        # Duplicate and conflict checks using DB
        close_conn = False
        conn = connection
        try:
            if conn is None:
                conn = get_connection(self.db_path)
                close_conn = True

            # check duplicate by category+problem
            cur = conn.execute(
                "SELECT id, repair_steps FROM problems WHERE LOWER(category)=? AND LOWER(problem)=?",
                (problem.category.lower(), problem.problem.lower()),
            )
            row = cur.fetchone()
            if row:
                issues.append("duplicate_record")
                # conflict: compare repair steps lists
                try:
                    existing_steps = []
                    import json

                    existing = row["repair_steps"]
                    if existing:
                        existing_steps = json.loads(existing) if isinstance(existing, str) else list(existing)
                except Exception:
                    existing_steps = []

                new_set = {s.strip().lower() for s in (problem.repair_steps or [])}
                exist_set = {s.strip().lower() for s in (existing_steps or [])}
                if new_set and exist_set:
                    overlap = len(new_set & exist_set) / max(1, len(new_set | exist_set))
                    if overlap < 0.5:
                        issues.append("conflicting_repairs")

            # basic relationship check: inspection steps should reference symptoms or causes
            inspect_text = " ".join(problem.inspection_steps or [])
            if inspect_text and not any(k.lower() in inspect_text.lower() for k in (problem.symptoms or []) + (problem.causes or [])):
                issues.append("inspection_not_linked_to_symptoms_or_causes")

        finally:
            if close_conn and conn:
                conn.close()

        valid = len(issues) == 0
        return {"valid": valid, "issues": issues}

    def generate_report(self, reports: list[dict[str, Any]], tag: str | None = None) -> str:
        """Write a validation report JSON to the packs directory and return path."""
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "generated_at": now,
            "tag": tag or "validation",
            "reports": reports,
        }
        out_dir = settings.packs_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        fname = f"validation_report_{tag or 'run'}_{datetime.now().strftime('%Y%m%dT%H%M%S')}.json"
        path = out_dir / fname
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return str(path)


__all__ = ["ValidationEngine"]
