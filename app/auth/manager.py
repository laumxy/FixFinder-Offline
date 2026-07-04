"""
User & Auth Manager — SQLite-backed user store with login/creation.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.auth.password import hash_password, verify_password
from app.auth.tokens import create_token
from app.database.db import get_connection
from fixfinder_engine.config import settings


class AuthManager:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.database_path

    # ── Login ─────────────────────────────────────────────────────────────────

    def login(self, username: str, password: str) -> dict[str, Any]:
        user = self._get_user(username)
        if not user:
            return {"success": False, "message": "User not found."}
        if not user["is_active"]:
            return {"success": False, "message": "Account is disabled."}
        if not verify_password(password, user["password_hash"]):
            return {"success": False, "message": "Incorrect password."}

        now = datetime.now(timezone.utc).isoformat()
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET last_login_at=? WHERE id=?",
                (now, user["id"]),
            )

        token = create_token(
            user_id=user["id"],
            username=user["username"],
            role=user["role"],
            organization_id=user["organization_id"],
        )
        return {
            "success": True,
            "token": token,
            "user_id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "organization_id": user["organization_id"],
            "message": "Login successful.",
        }

    # ── User CRUD ─────────────────────────────────────────────────────────────

    def create_user(
        self,
        username: str,
        password: str,
        full_name: str = "",
        email: str = "",
        role: str = "technician",
        organization_id: int | None = None,
        license_id: int | None = None,
    ) -> dict[str, Any]:
        if self._get_user(username):
            return {"success": False, "message": f"Username '{username}' already exists."}

        password_hash = hash_password(password)
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO users
                    (username, password_hash, full_name, email, role,
                     organization_id, license_id, is_active)
                VALUES (?,?,?,?,?,?,?,1)
                """,
                (username, password_hash, full_name, email, role,
                 organization_id, license_id),
            )
            new_id = int(cursor.lastrowid)
        return {
            "success": True,
            "user_id": new_id,
            "username": username,
            "role": role,
            "message": "User created successfully.",
        }

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        if not self.db_path.exists():
            return None
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT id, username, full_name, email, role, organization_id, "
                "is_active, last_login_at, created_at FROM users WHERE id=?",
                (user_id,),
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def list_users(
        self, organization_id: int | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        if not self.db_path.exists():
            return []
        with get_connection(self.db_path) as conn:
            if organization_id is not None:
                rows = conn.execute(
                    "SELECT id, username, full_name, email, role, organization_id, "
                    "is_active, last_login_at FROM users WHERE organization_id=? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (organization_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, username, full_name, email, role, organization_id, "
                    "is_active, last_login_at FROM users ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def deactivate_user(self, user_id: int) -> bool:
        with get_connection(self.db_path) as conn:
            conn.execute("UPDATE users SET is_active=0 WHERE id=?", (user_id,))
        return True

    def change_password(self, user_id: int, new_password: str) -> bool:
        hashed = hash_password(new_password)
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET password_hash=? WHERE id=?", (hashed, user_id)
            )
        return True

    # ── Role CRUD ─────────────────────────────────────────────────────────────

    def create_role(
        self, name: str, permissions: list[str], description: str = ""
    ) -> dict[str, Any]:
        with get_connection(self.db_path) as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO roles (name, permissions, description) VALUES (?,?,?)",
                    (name, json.dumps(permissions), description),
                )
                return {"success": True, "role_id": int(cursor.lastrowid), "name": name}
            except Exception as exc:
                return {"success": False, "message": str(exc)}

    def list_roles(self) -> list[dict[str, Any]]:
        if not self.db_path.exists():
            return []
        with get_connection(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM roles ORDER BY name").fetchall()
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "permissions": json.loads(r["permissions"]),
                "description": r["description"],
            }
            for r in rows
        ]

    # ── Private ───────────────────────────────────────────────────────────────

    def _get_user(self, username: str) -> dict[str, Any] | None:
        if not self.db_path.exists():
            return None
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username=?", (username,)
            ).fetchone()
        if not row:
            return None
        return dict(row)
