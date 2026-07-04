"""
Analytics Tracker — offline-first event logging and aggregation.

All data stays local in SQLite. No network calls are made.
The tracker is safe to call from any request context.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.database.db import (
    fetch_analytics_summary,
    get_connection,
    insert_analytics_event,
)
from app.utils.logger import get_logger
from fixfinder_engine.config import settings


logger = get_logger(__name__)

# Thread-local write lock so concurrent requests don't interleave events.
_lock = threading.Lock()


class AnalyticsTracker:
    """Thin wrapper around the analytics_events table."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.database_path

    # ── Event recording ───────────────────────────────────────────────────────

    def record_diagnose(
        self,
        category: str,
        problem: str,
        confidence: float,
        language: str = "en",
        user_id: int | None = None,
        organization_id: int | None = None,
        knowledge_version: str = "",
        session_id: str = "",
    ) -> None:
        if not settings.analytics_enabled:
            return
        self._write(
            event_type="diagnose",
            category=category,
            problem=problem,
            confidence=confidence,
            language=language,
            user_id=user_id,
            organization_id=organization_id,
            knowledge_version=knowledge_version,
            session_id=session_id,
        )

    def record_learn(
        self,
        accepted: int,
        rejected: int,
        knowledge_version: str = "",
        user_id: int | None = None,
    ) -> None:
        if not settings.analytics_enabled:
            return
        self._write(
            event_type="learn",
            category="",
            problem=f"accepted={accepted} rejected={rejected}",
            confidence=float(accepted),
            knowledge_version=knowledge_version,
            user_id=user_id,
        )

    def record_license_event(
        self,
        event_type: str,
        license_type: str = "",
        user_id: int | None = None,
    ) -> None:
        if not settings.analytics_enabled:
            return
        self._write(
            event_type=event_type,
            category=license_type,
            problem="",
            confidence=0.0,
            user_id=user_id,
        )

    def record_pack_install(self, pack_id: str, record_count: int) -> None:
        if not settings.analytics_enabled:
            return
        self._write(
            event_type="pack_install",
            category="knowledge_pack",
            problem=pack_id,
            confidence=float(record_count),
        )

    # ── Aggregation ───────────────────────────────────────────────────────────

    def summary(self) -> dict[str, Any]:
        return fetch_analytics_summary(self.db_path)

    def category_stats(self) -> list[dict[str, Any]]:
        if not self.db_path.exists():
            return []
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT
                    category,
                    COUNT(*) AS total_diagnoses,
                    AVG(confidence) AS avg_confidence,
                    MAX(created_at) AS last_used
                FROM analytics_events
                WHERE event_type = 'diagnose' AND category != ''
                GROUP BY category
                ORDER BY total_diagnoses DESC
                """
            ).fetchall()
        return [
            {
                "category": r["category"],
                "total_diagnoses": r["total_diagnoses"],
                "avg_confidence": round(float(r["avg_confidence"] or 0), 2),
                "last_used": r["last_used"],
            }
            for r in rows
        ]

    def daily_activity(self, days: int = 30) -> list[dict[str, Any]]:
        if not self.db_path.exists():
            return []
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT
                    DATE(created_at) AS day,
                    COUNT(*) AS events,
                    SUM(CASE WHEN event_type='diagnose' THEN 1 ELSE 0 END) AS diagnoses,
                    SUM(CASE WHEN event_type='learn' THEN 1 ELSE 0 END) AS learns
                FROM analytics_events
                WHERE created_at >= DATE('now', ?)
                GROUP BY day
                ORDER BY day DESC
                """,
                (f"-{days} days",),
            ).fetchall()
        return [
            {
                "day": r["day"],
                "events": r["events"],
                "diagnoses": r["diagnoses"],
                "learns": r["learns"],
            }
            for r in rows
        ]

    def confidence_distribution(self) -> dict[str, int]:
        if not self.db_path.exists():
            return {}
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT
                    CASE
                        WHEN confidence >= 90 THEN '90-100%'
                        WHEN confidence >= 75 THEN '75-89%'
                        WHEN confidence >= 60 THEN '60-74%'
                        WHEN confidence >= 40 THEN '40-59%'
                        ELSE 'below 40%'
                    END AS bucket,
                    COUNT(*) AS cnt
                FROM analytics_events
                WHERE event_type = 'diagnose' AND confidence > 0
                GROUP BY bucket
                ORDER BY bucket DESC
                """
            ).fetchall()
        return {r["bucket"]: r["cnt"] for r in rows}

    # ── Private ───────────────────────────────────────────────────────────────

    def _write(
        self,
        event_type: str,
        category: str = "",
        problem: str = "",
        confidence: float = 0.0,
        language: str = "en",
        user_id: int | None = None,
        organization_id: int | None = None,
        knowledge_version: str = "",
        session_id: str = "",
    ) -> None:
        try:
            with _lock:
                insert_analytics_event(
                    db_path=self.db_path,
                    event_type=event_type,
                    category=category,
                    problem=problem[:256],
                    confidence=confidence,
                    language=language,
                    user_id=user_id,
                    organization_id=organization_id,
                    knowledge_version=knowledge_version,
                    session_id=session_id,
                )
        except Exception as exc:
            logger.warning("Analytics write failed: %s", exc)


# Module-level singleton so the pipeline can import it directly.
tracker = AnalyticsTracker()
