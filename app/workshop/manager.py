"""
Workshop Manager — customers, equipment, and repair job history.
All data is stored locally in SQLite in the workshop_* tables.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.database.db import get_connection
from fixfinder_engine.config import settings

# ── Schema SQL ────────────────────────────────────────────────────────────────
WORKSHOP_SCHEMA = """
CREATE TABLE IF NOT EXISTS workshop_customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    organization_id INTEGER,
    created_by INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_wc_name ON workshop_customers(name);
CREATE INDEX IF NOT EXISTS idx_wc_phone ON workshop_customers(phone);
CREATE INDEX IF NOT EXISTS idx_wc_org ON workshop_customers(organization_id);

CREATE TABLE IF NOT EXISTS workshop_equipment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES workshop_customers(id),
    name TEXT NOT NULL,
    model TEXT NOT NULL DEFAULT '',
    serial_number TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'general',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_we_customer ON workshop_equipment(customer_id);
CREATE INDEX IF NOT EXISTS idx_we_category ON workshop_equipment(category);

CREATE TABLE IF NOT EXISTS workshop_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES workshop_customers(id),
    equipment_id INTEGER REFERENCES workshop_equipment(id),
    technician_id INTEGER,
    organization_id INTEGER,
    problem_description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'general',
    diagnosis_result TEXT NOT NULL DEFAULT '{}',
    repair_performed TEXT NOT NULL DEFAULT '',
    parts_used TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'open',
    priority TEXT NOT NULL DEFAULT 'normal',
    estimated_cost TEXT NOT NULL DEFAULT 'unknown',
    actual_cost REAL NOT NULL DEFAULT 0.0,
    opened_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at TEXT,
    notes TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_wj_customer ON workshop_jobs(customer_id);
CREATE INDEX IF NOT EXISTS idx_wj_status ON workshop_jobs(status);
CREATE INDEX IF NOT EXISTS idx_wj_technician ON workshop_jobs(technician_id);
CREATE INDEX IF NOT EXISTS idx_wj_org ON workshop_jobs(organization_id);
CREATE INDEX IF NOT EXISTS idx_wj_opened ON workshop_jobs(opened_at);
"""


def ensure_workshop_schema(db_path: Path) -> None:
    with get_connection(db_path) as conn:
        conn.executescript(WORKSHOP_SCHEMA)


class WorkshopManager:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.database_path
        ensure_workshop_schema(self.db_path)

    # ── Customers ─────────────────────────────────────────────────────────────

    def create_customer(
        self,
        name: str,
        phone: str = "",
        email: str = "",
        address: str = "",
        notes: str = "",
        organization_id: int | None = None,
        created_by: int | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO workshop_customers
                    (name, phone, email, address, notes, organization_id,
                     created_by, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (name, phone, email, address, notes, organization_id,
                 created_by, now, now),
            )
            new_id = int(cursor.lastrowid)
        return {"customer_id": new_id, "name": name, "success": True}

    def get_customer(self, customer_id: int) -> dict[str, Any] | None:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM workshop_customers WHERE id=?", (customer_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_customers(
        self,
        organization_id: int | None = None,
        search: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as conn:
            if search:
                rows = conn.execute(
                    "SELECT * FROM workshop_customers WHERE "
                    "(name LIKE ? OR phone LIKE ? OR email LIKE ?) "
                    "ORDER BY name LIMIT ?",
                    (f"%{search}%", f"%{search}%", f"%{search}%", limit),
                ).fetchall()
            elif organization_id is not None:
                rows = conn.execute(
                    "SELECT * FROM workshop_customers WHERE organization_id=? "
                    "ORDER BY name LIMIT ?",
                    (organization_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM workshop_customers ORDER BY name LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    # ── Equipment ─────────────────────────────────────────────────────────────

    def add_equipment(
        self,
        customer_id: int,
        name: str,
        model: str = "",
        serial_number: str = "",
        category: str = "general",
        notes: str = "",
    ) -> dict[str, Any]:
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO workshop_equipment
                    (customer_id, name, model, serial_number, category, notes)
                VALUES (?,?,?,?,?,?)
                """,
                (customer_id, name, model, serial_number, category, notes),
            )
            new_id = int(cursor.lastrowid)
        return {"equipment_id": new_id, "name": name, "success": True}

    def list_equipment(self, customer_id: int) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM workshop_equipment WHERE customer_id=? ORDER BY name",
                (customer_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Jobs ──────────────────────────────────────────────────────────────────

    def open_job(
        self,
        customer_id: int,
        problem_description: str,
        equipment_id: int | None = None,
        technician_id: int | None = None,
        organization_id: int | None = None,
        category: str = "general",
        estimated_cost: str = "unknown",
        priority: str = "normal",
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO workshop_jobs
                    (customer_id, equipment_id, technician_id, organization_id,
                     problem_description, category, estimated_cost, priority,
                     status, opened_at)
                VALUES (?,?,?,?,?,?,?,?,'open',?)
                """,
                (customer_id, equipment_id, technician_id, organization_id,
                 problem_description, category, estimated_cost, priority, now),
            )
            new_id = int(cursor.lastrowid)
        return {"job_id": new_id, "status": "open", "success": True}

    def update_job(
        self,
        job_id: int,
        status: str | None = None,
        repair_performed: str | None = None,
        parts_used: list[str] | None = None,
        actual_cost: float | None = None,
        diagnosis_result: dict | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        fields, values = [], []
        if status is not None:
            fields.append("status=?")
            values.append(status)
            if status == "closed":
                fields.append("closed_at=?")
                values.append(datetime.now(timezone.utc).isoformat())
        if repair_performed is not None:
            fields.append("repair_performed=?")
            values.append(repair_performed)
        if parts_used is not None:
            fields.append("parts_used=?")
            values.append(json.dumps(parts_used))
        if actual_cost is not None:
            fields.append("actual_cost=?")
            values.append(actual_cost)
        if diagnosis_result is not None:
            fields.append("diagnosis_result=?")
            values.append(json.dumps(diagnosis_result))
        if notes is not None:
            fields.append("notes=?")
            values.append(notes)
        if not fields:
            return {"success": False, "message": "Nothing to update."}
        values.append(job_id)
        with get_connection(self.db_path) as conn:
            conn.execute(
                f"UPDATE workshop_jobs SET {', '.join(fields)} WHERE id=?",
                values,
            )
        return {"success": True, "job_id": job_id}

    def get_job(self, job_id: int) -> dict[str, Any] | None:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM workshop_jobs WHERE id=?", (job_id,)
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["parts_used"] = json.loads(d.get("parts_used") or "[]")
        d["diagnosis_result"] = json.loads(d.get("diagnosis_result") or "{}")
        return d

    def list_jobs(
        self,
        customer_id: int | None = None,
        technician_id: int | None = None,
        organization_id: int | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        clauses, params = [], []
        if customer_id is not None:
            clauses.append("customer_id=?"); params.append(customer_id)
        if technician_id is not None:
            clauses.append("technician_id=?"); params.append(technician_id)
        if organization_id is not None:
            clauses.append("organization_id=?"); params.append(organization_id)
        if status:
            clauses.append("status=?"); params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT * FROM workshop_jobs {where} "
                "ORDER BY opened_at DESC LIMIT ?",
                params,
            ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["parts_used"] = json.loads(d.get("parts_used") or "[]")
            d["diagnosis_result"] = json.loads(d.get("diagnosis_result") or "{}")
            result.append(d)
        return result

    def summary(
        self, organization_id: int | None = None
    ) -> dict[str, Any]:
        clauses, params = [], []
        if organization_id is not None:
            clauses.append("organization_id=?"); params.append(organization_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with get_connection(self.db_path) as conn:
            total_jobs = int(
                conn.execute(f"SELECT COUNT(*) FROM workshop_jobs {where}", params).fetchone()[0]
            )
            open_jobs = int(
                conn.execute(
                    f"SELECT COUNT(*) FROM workshop_jobs {where + ' AND' if where else 'WHERE'} status='open'",
                    params,
                ).fetchone()[0]
            )
            total_customers = int(
                conn.execute("SELECT COUNT(*) FROM workshop_customers").fetchone()[0]
            )
            revenue = conn.execute(
                f"SELECT SUM(actual_cost) FROM workshop_jobs {where}", params
            ).fetchone()[0]
        return {
            "total_jobs": total_jobs,
            "open_jobs": open_jobs,
            "closed_jobs": total_jobs - open_jobs,
            "total_customers": total_customers,
            "total_revenue": round(float(revenue or 0), 2),
        }
