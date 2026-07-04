"""
Password hashing using Python's stdlib hashlib (no bcrypt dependency).
Uses PBKDF2-HMAC-SHA256 with a random salt — secure for offline use.
"""
from __future__ import annotations

import hashlib
import hmac
import os


_ITERATIONS = 260_000
_HASH_ALGO  = "sha256"
_KEY_LEN    = 32


def hash_password(plain: str) -> str:
    """Return a salted hash string: hex_salt$hex_hash"""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        _HASH_ALGO,
        plain.encode("utf-8"),
        salt,
        _ITERATIONS,
        dklen=_KEY_LEN,
    )
    return f"{salt.hex()}${digest.hex()}"


def verify_password(plain: str, stored: str) -> bool:
    """Return True if plain matches the stored hash string."""
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, AttributeError):
        return False

    candidate = hashlib.pbkdf2_hmac(
        _HASH_ALGO,
        plain.encode("utf-8"),
        salt,
        _ITERATIONS,
        dklen=_KEY_LEN,
    )
    return hmac.compare_digest(expected, candidate)
