"""
License store — all SQLite reads/writes for the licensing engine.
Keeps DB logic separate from business logic.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.licensing.models import LicenseRecord, LicenseStatus, LicenseType
from app.database.db import get_connection


class LicenseStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    # ── License CRUD ──────────────────────────────────────────────────────────

    def get_by_key(self, license_key: str) -> LicenseRecord | None:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM licenses WHERE license_key=?", (license_key,)
            ).fetchone()
        return self._row_to_record(row) if row else None

    def get_by_id(self, license_id: int) -> LicenseRecord | None:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM licenses WHERE id=?", (license_id,)
            ).fetchone()
        return self._row_to_record(row) if row else None

    def insert_license(
        self,
        license_key: str,
        license_type: LicenseType,
        owner_name: str = "",
        owner_email: str = "",
        expires_at: str | None = None,
        organization_id: int | None = None,
        notes: str = "",
    ) -> LicenseRecord:
        features = json.dumps(
            [f.value if hasattr(f, "value") else f
             for f in self._default_features(license_type)],
            ensure_ascii=False,
        )
        from app.licensing.models import LICENSE_FEATURES, MAX_DEVICES
        feat_list = [f for f in LICENSE_FEATURES[license_type]]
        max_dev = MAX_DEVICES[license_type]

        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO licenses
                    (license_key, license_type, status, owner_name, owner_email,
                     organization_id, features, allowed_industries, max_devices,
                     expires_at, notes)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    license_key, license_type.value, LicenseStatus.UNACTIVATED.value,
                    owner_name, owner_email, organization_id,
                    json.dumps(feat_list), "[]", max_dev,
                    expires_at, notes,
                ),
            )
            new_id = int(cursor.lastrowid)
        return self.get_by_id(new_id)

    def activate(self, license_id: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE licenses SET status=?, activated_at=?, last_validated_at=? WHERE id=?",
                (LicenseStatus.ACTIVE.value, now, now, license_id),
            )

    def mark_validated(self, license_id: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE licenses SET last_validated_at=? WHERE id=?",
                (now, license_id),
            )

    def set_status(self, license_id: int, status: LicenseStatus) -> None:
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE licenses SET status=? WHERE id=?",
                (status.value, license_id),
            )

    # ── Device CRUD ───────────────────────────────────────────────────────────

    def count_devices(self, license_id: int) -> int:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM license_devices WHERE license_id=?",
                (license_id,),
            ).fetchone()
        return int(row[0])

    def device_exists(self, license_id: int, fingerprint: str) -> bool:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT id FROM license_devices WHERE license_id=? AND device_fingerprint=?",
                (license_id, fingerprint),
            ).fetchone()
        return row is not None

    def register_device(
        self, license_id: int, fingerprint: str, device_name: str = ""
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO license_devices
                    (license_id, device_fingerprint, device_name,
                     registered_at, last_seen_at)
                VALUES (?,?,?,?,?)
                ON CONFLICT(license_id, device_fingerprint)
                DO UPDATE SET last_seen_at=excluded.last_seen_at
                """,
                (license_id, fingerprint, device_name, now, now),
            )

    def list_devices(self, license_id: int) -> list[dict]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM license_devices WHERE license_id=? ORDER BY registered_at",
                (license_id,),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "device_fingerprint": r["device_fingerprint"][:12] + "…",
                "device_name": r["device_name"],
                "registered_at": r["registered_at"],
                "last_seen_at": r["last_seen_at"],
            }
            for r in rows
        ]

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> LicenseRecord:
        return LicenseRecord(
            id=row["id"],
            license_key=row["license_key"],
            license_type=LicenseType(row["license_type"]),
            status=LicenseStatus(row["status"]),
            owner_name=row["owner_name"],
            owner_email=row["owner_email"],
            organization_id=row["organization_id"],
            features=json.loads(row["features"]),
            allowed_industries=json.loads(row["allowed_industries"]),
            max_devices=row["max_devices"],
            issued_at=row["issued_at"],
            expires_at=row["expires_at"],
            activated_at=row["activated_at"],
            last_validated_at=row["last_validated_at"],
            notes=row["notes"],
        )

    @staticmethod
    def _default_features(license_type: LicenseType) -> list[str]:
        from app.licensing.models import LICENSE_FEATURES
        return LICENSE_FEATURES[license_type]
