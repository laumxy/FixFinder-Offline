"""
License Validator — offline license activation and validation logic.
All checks run against the local SQLite database; no network calls.
"""
from __future__ import annotations

import hashlib
import secrets
import string
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.licensing.device import get_device_fingerprint
from app.licensing.models import (
    LICENSE_FEATURES,
    LicenseRecord,
    LicenseStatus,
    LicenseType,
    ValidationResult,
)
from app.licensing.store import LicenseStore
from fixfinder_engine.config import settings


def _generate_license_key(license_type: LicenseType) -> str:
    """Generate a deterministic-format license key: FF-<TYPE>-XXXX-XXXX-XXXX."""
    prefix = {
        LicenseType.PERSONAL: "P",
        LicenseType.TECHNICIAN: "T",
        LicenseType.WORKSHOP: "W",
        LicenseType.ENTERPRISE: "E",
    }[license_type]
    alphabet = string.ascii_uppercase + string.digits
    segments = [
        "".join(secrets.choice(alphabet) for _ in range(4))
        for _ in range(3)
    ]
    return f"FF-{prefix}-{'-'.join(segments)}"


class LicenseValidator:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.database_path
        self.store = LicenseStore(self.db_path)

    # ── Activation ────────────────────────────────────────────────────────────

    def activate(
        self,
        license_key: str,
        device_name: str = "",
        owner_name: str = "",
        owner_email: str = "",
    ) -> ValidationResult:
        record = self.store.get_by_key(license_key.strip().upper())
        if not record:
            # Auto-create a personal license for demo/offline-first mode
            record = self._create_demo_license(license_key.strip().upper())

        fingerprint = get_device_fingerprint()

        if record.status == LicenseStatus.SUSPENDED:
            return ValidationResult(
                valid=False,
                license_key=license_key,
                license_type=record.license_type.value,
                status=record.status.value,
                features=[],
                days_until_expiry=None,
                message="License is suspended.",
            )

        if record.expires_at:
            expiry = datetime.fromisoformat(record.expires_at)
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expiry:
                self.store.set_status(record.id, LicenseStatus.EXPIRED)
                return ValidationResult(
                    valid=False,
                    license_key=license_key,
                    license_type=record.license_type.value,
                    status=LicenseStatus.EXPIRED.value,
                    features=[],
                    days_until_expiry=0,
                    message="License has expired.",
                )

        # Check device cap (skip if already registered on this device)
        if not self.store.device_exists(record.id, fingerprint):
            device_count = self.store.count_devices(record.id)
            if device_count >= record.max_devices:
                return ValidationResult(
                    valid=False,
                    license_key=license_key,
                    license_type=record.license_type.value,
                    status=record.status.value,
                    features=[],
                    days_until_expiry=record.days_until_expiry(),
                    message=(
                        f"Device limit reached ({record.max_devices}). "
                        "Deactivate another device or upgrade your license."
                    ),
                )
            self.store.register_device(record.id, fingerprint, device_name or "")

        if record.status == LicenseStatus.UNACTIVATED:
            self.store.activate(record.id)
            record = self.store.get_by_id(record.id)
        else:
            self.store.mark_validated(record.id)

        return ValidationResult(
            valid=True,
            license_key=license_key,
            license_type=record.license_type.value,
            status=LicenseStatus.ACTIVE.value,
            features=record.features,
            days_until_expiry=record.days_until_expiry(),
            message="License activated successfully.",
            device_registered=True,
        )

    # ── Validation (fast offline check on every startup) ─────────────────────

    def validate_current_device(self, license_key: str) -> ValidationResult:
        record = self.store.get_by_key(license_key.strip().upper())
        if not record:
            return ValidationResult(
                valid=False,
                license_key=license_key,
                license_type="unknown",
                status=LicenseStatus.INVALID.value,
                features=[],
                days_until_expiry=None,
                message="License key not found.",
            )

        fingerprint = get_device_fingerprint()
        device_ok = self.store.device_exists(record.id, fingerprint)
        if not device_ok:
            return ValidationResult(
                valid=False,
                license_key=license_key,
                license_type=record.license_type.value,
                status=LicenseStatus.INVALID.value,
                features=[],
                days_until_expiry=None,
                message="This device is not registered for the provided license.",
            )

        if not record.is_valid():
            return ValidationResult(
                valid=False,
                license_key=license_key,
                license_type=record.license_type.value,
                status=record.status.value,
                features=[],
                days_until_expiry=record.days_until_expiry(),
                message=f"License is {record.status.value}.",
            )

        self.store.mark_validated(record.id)
        return ValidationResult(
            valid=True,
            license_key=license_key,
            license_type=record.license_type.value,
            status=LicenseStatus.ACTIVE.value,
            features=record.features,
            days_until_expiry=record.days_until_expiry(),
            message="License valid.",
            device_registered=True,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _create_demo_license(self, license_key: str) -> LicenseRecord:
        """
        Offline-first: if a key is unknown we create a personal demo license
        so the platform works without a licensing server.
        """
        expires_at = (
            datetime.now(timezone.utc) + timedelta(days=365)
        ).isoformat()
        return self.store.insert_license(
            license_key=license_key,
            license_type=LicenseType.PERSONAL,
            owner_name="Demo User",
            expires_at=expires_at,
            notes="Auto-created offline demo license.",
        )

    def create_license(
        self,
        license_type: LicenseType,
        owner_name: str = "",
        owner_email: str = "",
        valid_days: int = 365,
        organization_id: int | None = None,
        notes: str = "",
    ) -> LicenseRecord:
        key = _generate_license_key(license_type)
        expires_at = (
            datetime.now(timezone.utc) + timedelta(days=valid_days)
        ).isoformat()
        return self.store.insert_license(
            license_key=key,
            license_type=license_type,
            owner_name=owner_name,
            owner_email=owner_email,
            expires_at=expires_at,
            organization_id=organization_id,
            notes=notes,
        )

    def list_devices(self, license_key: str) -> list[dict]:
        record = self.store.get_by_key(license_key.strip().upper())
        if not record:
            return []
        return self.store.list_devices(record.id)
