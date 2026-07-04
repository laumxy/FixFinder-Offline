from pydantic import BaseModel, Field


class KnowledgeProblem(BaseModel):
    category: str = Field(..., min_length=2)
    problem: str = Field(..., min_length=3)
    aliases: list[str] = Field(default_factory=list)
    symptoms: list[str] = Field(..., min_length=1)
    causes: list[str] = Field(..., min_length=1)
    inspection_steps: list[str] = Field(..., min_length=1)
    repair_steps: list[str] = Field(..., min_length=1)
    tools: list[str] = Field(..., min_length=1)
    safety: list[str] = Field(..., min_length=1)
    prevention: list[str] = Field(default_factory=list)
    maintenance: list[str] = Field(default_factory=list)
    difficulty: str = "moderate"
    risk_level: str = "medium"
    estimated_time: str = "unknown"
    estimated_cost: str = "unknown"
    source_type: str = "seed"
    source_url: str = ""
    reliability_score: float = Field(default=1.0, ge=0.0, le=1.0)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    knowledge_version: str = "v1.0"

    def search_text(self) -> str:
        values = [
            self.category,
            self.problem,
            " ".join(self.aliases),
            " ".join(self.symptoms),
            " ".join(self.causes),
            " ".join(self.inspection_steps),
            " ".join(self.repair_steps),
            " ".join(self.tools),
            " ".join(self.safety),
            " ".join(self.prevention),
            " ".join(self.maintenance),
            self.difficulty,
            self.risk_level,
            self.estimated_time,
            self.source_type,
        ]
        return " ".join(v for v in values if v).lower()


class LearningSource(BaseModel):
    url: str = ""
    text: str = ""
    category: str = "general"
    source_type: str = "manual"


class LearningRequest(BaseModel):
    sources: list[LearningSource] = Field(..., min_length=1)
    min_reliability: float = Field(default=0.55, ge=0.0, le=1.0)


class DiagnoseRequest(BaseModel):
    problem: str = Field(..., min_length=3, max_length=2000)
    language: str = Field(default="en", max_length=10)
    session_id: str = Field(default="", max_length=128)
    user_id: int | None = None


class ConverseRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(default="", max_length=128)
    language: str = Field(default="en", max_length=10)


class LicenseActivateRequest(BaseModel):
    license_key: str = Field(..., min_length=8, max_length=128)
    device_name: str = Field(default="", max_length=128)
    owner_name: str = Field(default="", max_length=128)
    owner_email: str = Field(default="", max_length=256)


class InstallPackRequest(BaseModel):
    pack_id: str = Field(..., min_length=2, max_length=64)
    file_path: str = Field(default="", max_length=512)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=4, max_length=256)


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6, max_length=256)
    full_name: str = Field(default="", max_length=128)
    email: str = Field(default="", max_length=256)
    role: str = Field(default="technician", max_length=32)
    organization_id: int | None = None


class ReportRequest(BaseModel):
    report_type: str = Field(default="diagnostic", max_length=32)
    format: str = Field(default="json", max_length=8)
    limit: int = Field(default=20, ge=1, le=200)
