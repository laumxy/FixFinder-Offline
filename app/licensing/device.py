"""
Device fingerprinting — produces a stable, anonymous hardware-based identifier
that works completely offline. No external calls are made.
"""
from __future__ import annotations

import hashlib
import platform
import socket
import uuid

from fixfinder_engine.config import settings


def _safe(fn) -> str:
    try:
        return str(fn()) or ""
    except Exception:
        return ""


def get_device_fingerprint() -> str:
    """Return a SHA-256 hex fingerprint for the current device."""
    components = [
        _safe(platform.node),
        _safe(lambda: platform.machine()),
        _safe(lambda: platform.processor()),
        _safe(lambda: str(uuid.getnode())),          # MAC address as integer
        _safe(lambda: socket.gethostname()),
        _safe(lambda: platform.system()),
        settings.device_fingerprint_salt,
    ]
    raw = "|".join(components)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_device_info() -> dict:
    return {
        "hostname": _safe(socket.gethostname),
        "platform": _safe(lambda: platform.system()),
        "machine": _safe(lambda: platform.machine()),
        "fingerprint": get_device_fingerprint(),
    }
