"""
Enterprise Manager — organizations, departments, branding, and role-permission management.
All state is stored in local SQLite.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.database.db import get_connection
from fixfinder_engine.config import settings

# ── Extended schema ───────────────────────────────────────────────────────────
ENTERPRISE_SCHEMA = """
CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    parent_department_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, name)
);
CREATE INDEX IF NOT EXISTS idx_dept_org ON departments(organization_id);
"""


def ensure_enterprise_schema(db_path: Path) -> None:
    with get_connection(db_path) as conn:
        conn.executescript(ENTERPRISE_SCHEMA)


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


class EnterpriseManager:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.database_path
        ensure_enterprise_schema(self.db_path)

    # ── Organizations ─────────────────────────────────────────────────────────

    def create_organization(
        self,
        name: str,
        license_id: int | None = None,
        brand_config: dict | None = None,
        deployment_config: dict | None = None,
    ) -> dict[str, Any]:
        slug = _slugify(name)
        now = datetime.now(timezone.utc).isoformat()
        with get_connection(self.db_path) as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO organizations
                        (name, slug, license_id, brand_config, deployment_config, created_at)
                    VALUES (?,?,?,?,?,?)
                    """,
                    (
                        name, slug, license_id,
                        json.dumps(brand_config or {}),
                        json.dumps(deployment_config or {}),
                        now,
                    ),
                )
                org_id = int(cursor.lastrowid)
            except Exception as exc:
                return {"success": False, "message": str(exc)}
        return {"success": True, "organization_id": org_id, "name": name, "slug": slug}

    def get_organization(self, org_id: int) -> dict[str, Any] | None:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM organizations WHERE id=?", (org_id,)
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["brand_config"] = json.loads(d.get("brand_config") or "{}")
        d["deployment_config"] = json.loads(d.get("deployment_config") or "{}")
        return d

    def list_organizations(self, limit: int = 100) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM organizations ORDER BY name LIMIT ?", (limit,)
            ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["brand_config"] = json.loads(d.get("brand_config") or "{}")
            d["deployment_config"] = json.loads(d.get("deployment_config") or "{}")
            result.append(d)
        return result

    def update_branding(self, org_id: int, brand_config: dict) -> dict[str, Any]:
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE organizations SET brand_config=? WHERE id=?",
                (json.dumps(brand_config), org_id),
            )
        return {"success": True, "organization_id": org_id}

    # ── Departments ───────────────────────────────────────────────────────────

    def create_department(
        self,
        organization_id: int,
        name: str,
        description: str = "",
        parent_department_id: int | None = None,
    ) -> dict[str, Any]:
        with get_connection(self.db_path) as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO departments
                        (organization_id, name, description, parent_department_id)
                    VALUES (?,?,?,?)
                    """,
                    (organization_id, name, description, parent_department_id),
                )
                dept_id = int(cursor.lastrowid)
            except Exception as exc:
                return {"success": False, "message": str(exc)}
        return {"success": True, "department_id": dept_id, "name": name}

    def list_departments(self, organization_id: int) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM departments WHERE organization_id=? ORDER BY name",
                (organization_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Role Permissions ──────────────────────────────────────────────────────

    DEFAULT_PERMISSIONS: dict[str, list[str]] = {
        "admin": [
            "diagnose", "learn", "manage_users", "manage_licenses", "view_analytics",
            "export_reports", "manage_organizations", "install_packs", "manage_roles",
        ],
        "technician": [
            "diagnose", "view_reports", "create_jobs", "update_jobs",
        ],
        "viewer": [
            "diagnose",
        ],
        "manager": [
            "diagnose", "learn", "view_analytics", "export_reports",
            "manage_users", "create_jobs", "update_jobs", "close_jobs",
        ],
    }

    def seed_default_roles(self) -> int:
        count = 0
        for role_name, permissions in self.DEFAULT_PERMISSIONS.items():
            with get_connection(self.db_path) as conn:
                existing = conn.execute(
                    "SELECT id FROM roles WHERE name=?", (role_name,)
                ).fetchone()
                if not existing:
                    conn.execute(
                        "INSERT INTO roles (name, permissions, description) VALUES (?,?,?)",
                        (role_name, json.dumps(permissions), f"Default {role_name} role"),
                    )
                    count += 1
        return count

    def get_permissions(self, role: str) -> list[str]:
        if not self.db_path.exists():
            return self.DEFAULT_PERMISSIONS.get(role, [])
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT permissions FROM roles WHERE name=?", (role,)
            ).fetchone()
        if row:
            return json.loads(row["permissions"])
        return self.DEFAULT_PERMISSIONS.get(role, [])

    def has_permission(self, role: str, permission: str) -> bool:
        return permission in self.get_permissions(role)

    def org_summary(self, org_id: int) -> dict[str, Any]:
        with get_connection(self.db_path) as conn:
            user_count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM users WHERE organization_id=?", (org_id,)
                ).fetchone()[0]
            )
            dept_count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM departments WHERE organization_id=?", (org_id,)
                ).fetchone()[0]
            )
        org = self.get_organization(org_id)
        return {
            "organization": org,
            "user_count": user_count,
            "department_count": dept_count,
        }
