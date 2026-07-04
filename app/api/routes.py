"""
FixFinder Offline AI Platform v3 — REST API
Implements all endpoints across all editions.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.analytics.tracker import tracker as analytics_tracker
from app.auth.manager import AuthManager
from app.auth.tokens import token_to_user
from app.core.pipeline import FixFinderPipeline
from app.database.db import latest_version, fetch_analytics_summary
from app.database.models import (
    ConverseRequest,
    DiagnoseRequest,
    LearningRequest,
    LicenseActivateRequest,
    LoginRequest,
    UserCreateRequest,
    InstallPackRequest,
    ReportRequest,
)
from app.enterprise.manager import EnterpriseManager
from app.knowledge.packs import KnowledgePackManager
from app.knowledge.updater import KnowledgeUpdater
from app.licensing.models import LicenseType
from app.licensing.validator import LicenseValidator
from app.localization.translator import localizer
from app.reporting.generator import ReportGenerator
from app.workshop.manager import WorkshopManager
from fixfinder_engine.config import settings

router = APIRouter()

# ── Singletons ────────────────────────────────────────────────────────────────
pipeline         = FixFinderPipeline()
knowledge_updater = KnowledgeUpdater()
license_validator = LicenseValidator()
auth_manager     = AuthManager()
enterprise_mgr   = EnterpriseManager()
workshop_mgr     = WorkshopManager()
pack_manager     = KnowledgePackManager()
report_generator = ReportGenerator()


# ── Auth helper ───────────────────────────────────────────────────────────────

def _current_user(authorization: str | None = Header(default=None)) -> dict[str, Any] | None:
    if not authorization:
        return None
    token = authorization.removeprefix("Bearer ").strip()
    return token_to_user(token)


def _require_auth(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = _current_user(authorization)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a valid Bearer token.",
        )
    return user


def _require_role(required: str, user: dict = Depends(_require_auth)) -> dict:
    if user["role"] not in (required, "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{required}' or 'admin' required.",
        )
    return user


# ── Root / Info ───────────────────────────────────────────────────────────────

@router.get("/")
def root() -> dict:
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "deploy_commit": "a7d0952-fix2",
        "endpoints": {
            "health":            "GET  /health",
            "diagnose":          "POST /diagnose",
            "learn":             "POST /learn",
            "knowledge_version": "GET  /knowledge/version",
            "install_pack":      "POST /install-pack",
            "build_pack":        "POST /build-pack",
            "list_packs":        "GET  /knowledge-packs",
            "activate_license":  "POST /activate-license",
            "login":             "POST /login",
            "create_user":       "POST /users",
            "list_users":        "GET  /users",
            "analytics":         "GET  /analytics",
            "reports":           "GET  /reports",
            "create_report":     "POST /reports",
            "organizations":     "GET  /orgs",
            "create_org":        "POST /orgs",
            "workshop_jobs":     "GET  /workshop/jobs",
            "create_job":        "POST /workshop/jobs",
            "customers":         "GET  /workshop/customers",
            "create_customer":   "POST /workshop/customers",
            "languages":         "GET  /localization/languages",
            "docs":              "GET  /docs",
        },
    }


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health")
def health() -> dict:
    return pipeline.health()


# ── Core: Diagnose ────────────────────────────────────────────────────────────

@router.post("/diagnose")
def diagnose(
    request: DiagnoseRequest,
    user: dict | None = Depends(_current_user),
) -> dict:
    user_id = user["user_id"] if user else None
    return pipeline.run(
        user_problem=request.problem,
        language=request.language,
        session_id=request.session_id,
        user_id=user_id,
    )


# ── Core: Converse (multi-turn diagnostic chat) ──────────────────────────────

@router.post("/converse")
def converse(
    request: ConverseRequest,
    user: dict | None = Depends(_current_user),
) -> dict:
    return pipeline.converse(
        message=request.message,
        session_id=request.session_id,
        language=request.language,
    )


# ── Core: Learn ───────────────────────────────────────────────────────────────

@router.post("/learn")
def learn(
    request: LearningRequest,
    user: dict | None = Depends(_current_user),
) -> dict:
    result = knowledge_updater.learn(request)
    if result.get("accepted", 0) > 0:
        user_id = user["user_id"] if user else None
        analytics_tracker.record_learn(
            accepted=result["accepted"],
            rejected=result.get("rejected", 0),
            knowledge_version=result.get("knowledge_version", ""),
            user_id=user_id,
        )
    return result


# ── Knowledge: Version ────────────────────────────────────────────────────────

@router.get("/knowledge/version")
def knowledge_version() -> dict:
    from app.database.db import fetch_all_problem_records
    records = fetch_all_problem_records(settings.database_path)
    return {
        "version": latest_version(settings.database_path),
        "problem_count": len(records),
        "categories": list({r["category"] for r in records}),
    }


# ── Knowledge Packs ───────────────────────────────────────────────────────────

@router.get("/knowledge-packs")
def list_packs(installed_only: bool = False) -> dict:
    return {"packs": pack_manager.list_packs(installed_only=installed_only)}


class BuildPackRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=128)
    description: str = Field(default="", max_length=512)
    industries: list[str] | None = None
    version: str = Field(default="1.0", max_length=16)


@router.post("/build-pack")
def build_pack(
    request: BuildPackRequest,
    user: dict = Depends(_require_auth),
) -> dict:
    return pack_manager.build_pack(
        name=request.name,
        description=request.description,
        industries=request.industries,
        version=request.version,
    )


@router.post("/install-pack")
def install_pack(request: InstallPackRequest) -> dict:
    result = pack_manager.install_pack(request.file_path)
    if result.get("success"):
        analytics_tracker.record_pack_install(
            pack_id=result.get("pack_id", ""),
            record_count=result.get("accepted", 0),
        )
    return result


# ── Licensing ─────────────────────────────────────────────────────────────────

@router.post("/activate-license")
def activate_license(request: LicenseActivateRequest) -> dict:
    result = license_validator.activate(
        license_key=request.license_key,
        device_name=request.device_name,
        owner_name=request.owner_name,
        owner_email=request.owner_email,
    )
    analytics_tracker.record_license_event(
        event_type="license_activate" if result.valid else "license_reject",
        license_type=result.license_type,
    )
    return {
        "valid": result.valid,
        "license_key": result.license_key,
        "license_type": result.license_type,
        "status": result.status,
        "features": result.features,
        "days_until_expiry": result.days_until_expiry,
        "device_registered": result.device_registered,
        "message": result.message,
    }


# ── Auth: Login ───────────────────────────────────────────────────────────────

@router.post("/login")
def login(request: LoginRequest) -> dict:
    result = auth_manager.login(request.username, request.password)
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result["message"],
        )
    return result


# ── Users ─────────────────────────────────────────────────────────────────────

@router.post("/users")
def create_user(
    request: UserCreateRequest,
) -> dict:
    result = auth_manager.create_user(
        username=request.username,
        password=request.password,
        full_name=request.full_name,
        email=request.email,
        role=request.role,
        organization_id=request.organization_id,
    )
    if not result["success"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result["message"])
    return result


@router.get("/users")
def list_users(
    organization_id: int | None = None,
    user: dict = Depends(_require_auth),
) -> dict:
    return {"users": auth_manager.list_users(organization_id=organization_id)}


@router.get("/users/{user_id}")
def get_user(user_id: int, user: dict = Depends(_require_auth)) -> dict:
    record = auth_manager.get_user_by_id(user_id)
    if not record:
        raise HTTPException(status_code=404, detail="User not found.")
    return record


# ── Analytics ─────────────────────────────────────────────────────────────────

@router.get("/analytics")
def analytics_summary(user: dict = Depends(_require_auth)) -> dict:
    return {
        "summary": analytics_tracker.summary(),
        "category_stats": analytics_tracker.category_stats(),
        "daily_activity": analytics_tracker.daily_activity(days=30),
        "confidence_distribution": analytics_tracker.confidence_distribution(),
    }


# ── Reports ───────────────────────────────────────────────────────────────────

@router.get("/reports")
def list_reports(
    report_type: str | None = None,
    limit: int = 50,
    user: dict = Depends(_require_auth),
) -> dict:
    return {"reports": report_generator.list_reports(report_type=report_type, limit=limit)}


class DiagnosticReportRequest(BaseModel):
    diagnosis: dict
    format: str = Field(default="json", max_length=4)


@router.post("/reports")
def create_report(
    request: DiagnosticReportRequest,
    user: dict = Depends(_require_auth),
) -> dict:
    return report_generator.create_diagnostic_report(
        diagnosis=request.diagnosis,
        fmt=request.format,
        user_id=user.get("user_id"),
        organization_id=user.get("organization_id"),
    )


@router.get("/reports/analytics")
def analytics_report(
    fmt: str = "json",
    user: dict = Depends(_require_auth),
) -> dict:
    return report_generator.create_analytics_report(
        fmt=fmt,
        user_id=user.get("user_id"),
        organization_id=user.get("organization_id"),
    )


# ── Enterprise: Organizations ─────────────────────────────────────────────────

class OrgCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=128)
    license_id: int | None = None
    brand_config: dict | None = None


@router.post("/orgs")
def create_org(
    request: OrgCreateRequest,
    user: dict = Depends(_require_auth),
) -> dict:
    result = enterprise_mgr.create_organization(
        name=request.name,
        license_id=request.license_id,
        brand_config=request.brand_config,
    )
    if not result["success"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result["message"])
    return result


@router.get("/orgs")
def list_orgs(user: dict = Depends(_require_auth)) -> dict:
    return {"organizations": enterprise_mgr.list_organizations()}


@router.get("/orgs/{org_id}")
def get_org(org_id: int, user: dict = Depends(_require_auth)) -> dict:
    org = enterprise_mgr.org_summary(org_id)
    if not org.get("organization"):
        raise HTTPException(status_code=404, detail="Organization not found.")
    return org


class DeptCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=128)
    description: str = Field(default="", max_length=512)
    parent_department_id: int | None = None


@router.post("/orgs/{org_id}/departments")
def create_department(
    org_id: int,
    request: DeptCreateRequest,
    user: dict = Depends(_require_auth),
) -> dict:
    return enterprise_mgr.create_department(
        organization_id=org_id,
        name=request.name,
        description=request.description,
        parent_department_id=request.parent_department_id,
    )


@router.get("/orgs/{org_id}/departments")
def list_departments(org_id: int, user: dict = Depends(_require_auth)) -> dict:
    return {"departments": enterprise_mgr.list_departments(org_id)}


# ── Workshop: Customers ───────────────────────────────────────────────────────

class CustomerCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    phone: str = Field(default="", max_length=32)
    email: str = Field(default="", max_length=256)
    address: str = Field(default="", max_length=512)
    notes: str = Field(default="", max_length=1000)


@router.post("/workshop/customers")
def create_customer(
    request: CustomerCreateRequest,
    user: dict = Depends(_require_auth),
) -> dict:
    return workshop_mgr.create_customer(
        name=request.name,
        phone=request.phone,
        email=request.email,
        address=request.address,
        notes=request.notes,
        organization_id=user.get("organization_id"),
        created_by=user.get("user_id"),
    )


@router.get("/workshop/customers")
def list_customers(
    search: str = "",
    limit: int = 100,
    user: dict = Depends(_require_auth),
) -> dict:
    return {
        "customers": workshop_mgr.list_customers(
            organization_id=user.get("organization_id"),
            search=search,
            limit=limit,
        )
    }


@router.get("/workshop/customers/{customer_id}")
def get_customer(customer_id: int, user: dict = Depends(_require_auth)) -> dict:
    customer = workshop_mgr.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")
    return customer


# ── Workshop: Equipment ───────────────────────────────────────────────────────

class EquipmentCreateRequest(BaseModel):
    customer_id: int
    name: str = Field(..., min_length=1, max_length=128)
    model: str = Field(default="", max_length=128)
    serial_number: str = Field(default="", max_length=128)
    category: str = Field(default="general", max_length=64)
    notes: str = Field(default="", max_length=1000)


@router.post("/workshop/equipment")
def add_equipment(
    request: EquipmentCreateRequest,
    user: dict = Depends(_require_auth),
) -> dict:
    return workshop_mgr.add_equipment(
        customer_id=request.customer_id,
        name=request.name,
        model=request.model,
        serial_number=request.serial_number,
        category=request.category,
        notes=request.notes,
    )


@router.get("/workshop/customers/{customer_id}/equipment")
def list_equipment(customer_id: int, user: dict = Depends(_require_auth)) -> dict:
    return {"equipment": workshop_mgr.list_equipment(customer_id)}


# ── Workshop: Jobs ────────────────────────────────────────────────────────────

class JobCreateRequest(BaseModel):
    customer_id: int
    problem_description: str = Field(..., min_length=3, max_length=2000)
    equipment_id: int | None = None
    category: str = Field(default="general", max_length=64)
    estimated_cost: str = Field(default="unknown", max_length=64)
    priority: str = Field(default="normal", max_length=32)


class JobUpdateRequest(BaseModel):
    status: str | None = None
    repair_performed: str | None = None
    parts_used: list[str] | None = None
    actual_cost: float | None = None
    notes: str | None = None


@router.post("/workshop/jobs")
def create_job(
    request: JobCreateRequest,
    user: dict = Depends(_require_auth),
) -> dict:
    return workshop_mgr.open_job(
        customer_id=request.customer_id,
        problem_description=request.problem_description,
        equipment_id=request.equipment_id,
        technician_id=user.get("user_id"),
        organization_id=user.get("organization_id"),
        category=request.category,
        estimated_cost=request.estimated_cost,
        priority=request.priority,
    )


@router.get("/workshop/jobs")
def list_jobs(
    status: str | None = None,
    customer_id: int | None = None,
    limit: int = 50,
    user: dict = Depends(_require_auth),
) -> dict:
    return {
        "jobs": workshop_mgr.list_jobs(
            customer_id=customer_id,
            technician_id=user.get("user_id") if user.get("role") == "technician" else None,
            organization_id=user.get("organization_id"),
            status=status,
            limit=limit,
        )
    }


@router.get("/workshop/jobs/{job_id}")
def get_job(job_id: int, user: dict = Depends(_require_auth)) -> dict:
    job = workshop_mgr.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@router.patch("/workshop/jobs/{job_id}")
def update_job(
    job_id: int,
    request: JobUpdateRequest,
    user: dict = Depends(_require_auth),
) -> dict:
    return workshop_mgr.update_job(
        job_id=job_id,
        status=request.status,
        repair_performed=request.repair_performed,
        parts_used=request.parts_used,
        actual_cost=request.actual_cost,
        notes=request.notes,
    )


@router.get("/workshop/summary")
def workshop_summary(user: dict = Depends(_require_auth)) -> dict:
    return workshop_mgr.summary(organization_id=user.get("organization_id"))


# ── Workshop: Report ──────────────────────────────────────────────────────────

@router.get("/workshop/report")
def workshop_report(
    fmt: str = "json",
    user: dict = Depends(_require_auth),
) -> dict:
    jobs = workshop_mgr.list_jobs(
        organization_id=user.get("organization_id"), limit=200
    )
    summary = workshop_mgr.summary(organization_id=user.get("organization_id"))
    return report_generator.create_workshop_report(
        jobs=jobs,
        summary=summary,
        fmt=fmt,
        user_id=user.get("user_id"),
        organization_id=user.get("organization_id"),
    )


# ── Localization ──────────────────────────────────────────────────────────────

@router.get("/localization/languages")
def list_languages() -> dict:
    return {"languages": localizer.supported()}


class TranslationRequest(BaseModel):
    language: str = Field(..., min_length=2, max_length=8)
    translations: dict[str, str]


@router.post("/localization/translations")
def add_translations(
    request: TranslationRequest,
    user: dict = Depends(_require_auth),
) -> dict:
    count = localizer.bulk_upsert(request.language, request.translations)
    return {"accepted": count, "language": request.language}
