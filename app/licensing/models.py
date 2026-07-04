"""
Licensing Engine — data models and enumerations.
All license state is persisted in SQLite; these are in-memory representations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class LicenseType(str, Enum):
    PERSONAL = "personal"
    TECHNICIAN = "technician"
    WORKSHOP = "workshop"
    ENTERPRISE = "enterprise"


class LicenseStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    UNACTIVATED = "unactivated"
    INVALID = "invalid"


# Features unlocked per license tier (cumulative upward).
LICENSE_FEATURES: dict[LicenseType, list[str]] = {
    LicenseType.PERSONAL: [
        "diagnose",
        "basic_report",
    ],
    LicenseType.TECHNICIAN: [
        "diagnose",
        "basic_report",
        "pdf_report",
        "knowledge_updates",
        "all_industries",
    ],
    LicenseType.WORKSHOP: [
        "diagnose",
        "basic_report",
        "pdf_report",
        "knowledge_updates",
        "all_industries",
        "repair_history",
        "customer_history",
        "equipment_history",
        "export_csv",
        "multi_technician",
    ],
    LicenseType.ENTERPRISE: [
        "diagnose",
        "basic_report",
        "pdf_report",
        "knowledge_updates",
        "all_industries",
        "repair_history",
        "customer_history",
        "equipment_history",
        "export_csv",
        "multi_technician",
        "enterprise_admin",
        "brand_customization",
        "private_knowledge_packs",
        "department_management",
        "role_permissions",
        "offline_deployment",
        "analytics_dashboard",
    ],
}

# Max simultaneous devices per tier
MAX_DEVICES: dict[LicenseType, int] = {
    LicenseType.PERSONAL: 1,
    LicenseType.TECHNICIAN: 2,
    LicenseType.WORKSHOP: 10,
    LicenseType.ENTERPRISE: 500,
}


@dataclass
class LicenseRecord:
    id: int
    license_key: str
    license_type: LicenseType
    status: LicenseStatus
    owner_name: str
    owner_email: str
    organization_id: int | None
    features: list[str]
    allowed_industries: list[str]
    max_devices: int
    issued_at: str
    expires_at: str | None
    activated_at: str | None
    last_validated_at: str | None
    notes: str

    def is_valid(self) -> bool:
        if self.status != LicenseStatus.ACTIVE:
            return False
        if self.expires_at:
            expiry = datetime.fromisoformat(self.expires_at)
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expiry:
                return False
        return True

    def has_feature(self, feature: str) -> bool:
        return feature in self.features

    def days_until_expiry(self) -> int | None:
        if not self.expires_at:
            return None
        expiry = datetime.fromisoformat(self.expires_at)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        delta = expiry - datetime.now(timezone.utc)
        return max(0, delta.days)


@dataclass
class ValidationResult:
    valid: bool
    license_key: str
    license_type: str
    status: str
    features: list[str]
    days_until_expiry: int | None
    message: str
    device_registered: bool = False
