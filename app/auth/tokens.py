"""
JWT-style tokens using stdlib only (hmac + hashlib).
Format: base64url(header).base64url(payload).base64url(signature)

No PyJWT dependency — fully offline, no pip install required.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fixfinder_engine.config import settings

_SECRET = settings.secret_key.encode("utf-8")
_ALGORITHM = "HS256"
_DEFAULT_TTL = 86_400  # 24 hours


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def _sign(message: str) -> str:
    sig = hmac.new(_SECRET, message.encode("utf-8"), hashlib.sha256).digest()
    return _b64encode(sig)


def create_token(
    user_id: int,
    username: str,
    role: str,
    organization_id: int | None = None,
    ttl: int = _DEFAULT_TTL,
) -> str:
    now = int(time.time())
    header = _b64encode(json.dumps({"alg": _ALGORITHM, "typ": "JWT"}).encode())
    payload = _b64encode(
        json.dumps(
            {
                "sub": user_id,
                "usr": username,
                "role": role,
                "org": organization_id,
                "iat": now,
                "exp": now + ttl,
            }
        ).encode()
    )
    message = f"{header}.{payload}"
    return f"{message}.{_sign(message)}"


def decode_token(token: str) -> dict[str, Any] | None:
    """Return the payload dict or None if invalid/expired."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts
        message = f"{header_b64}.{payload_b64}"
        expected_sig = _sign(message)
        if not hmac.compare_digest(expected_sig, sig_b64):
            return None
        payload = json.loads(_b64decode(payload_b64))
        if int(time.time()) > payload.get("exp", 0):
            return None
        return payload
    except Exception:
        return None


def token_to_user(token: str) -> dict[str, Any] | None:
    """Return a normalised user dict extracted from a valid token."""
    payload = decode_token(token)
    if not payload:
        return None
    return {
        "user_id": payload.get("sub"),
        "username": payload.get("usr"),
        "role": payload.get("role", "technician"),
        "organization_id": payload.get("org"),
    }
