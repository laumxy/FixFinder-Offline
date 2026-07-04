import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseModel):
    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "FIXFINDER OFFLINE AI PLATFORM v3"
    app_version: str = "3.0.0"
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False
    debug: bool = False
    secret_key: str = "fixfinder-offline-secret-change-in-production"

    # ── Paths ─────────────────────────────────────────────────────────────────
    database_path: Path = Field(default=PROJECT_ROOT / "data" / "fixfinder.db")
    seed_data_path: Path = Field(default=PROJECT_ROOT / "data" / "seed_data.json")
    faiss_index_path: Path = Field(default=PROJECT_ROOT / "embeddings" / "index.faiss")
    faiss_metadata_path: Path = Field(default=PROJECT_ROOT / "embeddings" / "metadata.json")
    packs_dir: Path = Field(default=PROJECT_ROOT / "data" / "packs")
    reports_dir: Path = Field(default=PROJECT_ROOT / "data" / "reports")
    analytics_dir: Path = Field(default=PROJECT_ROOT / "data" / "analytics")
    licenses_dir: Path = Field(default=PROJECT_ROOT / "data" / "licenses")

    # ── Embedding / FAISS ─────────────────────────────────────────────────────
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    min_semantic_score: float = 0.28
    retrieval_limit: int = 5

    # ── Ollama / Qwen ─────────────────────────────────────────────────────────
    ollama_url: str = "http://localhost:11434/api/generate"
    ollama_model: str = "qwen2.5:7b"
    ollama_timeout_seconds: int = 45
    ollama_temperature: float = 0.2
    ollama_num_predict: int = 700
    use_ollama: bool = True

    # ── Diagnostic ────────────────────────────────────────────────────────────
    confidence_threshold: float = 80.0

    # ── Licensing ─────────────────────────────────────────────────────────────
    license_validation_enabled: bool = True
    license_grace_days: int = 3
    device_fingerprint_salt: str = "fixfinder-device-salt-v3"

    # ── Localization ──────────────────────────────────────────────────────────
    default_language: str = "en"
    supported_languages: list[str] = Field(
        default=["en", "sw", "fr", "ar", "lg", "ach"]
    )

    # ── Analytics ─────────────────────────────────────────────────────────────
    analytics_enabled: bool = True
    analytics_flush_interval_minutes: int = 10

    # ── Reporting ─────────────────────────────────────────────────────────────
    report_pdf_enabled: bool = True
    report_company_name: str = "FixFinder"
    report_logo_path: Path = Field(default=PROJECT_ROOT / "data" / "logo.png")

    # ── Enterprise ────────────────────────────────────────────────────────────
    enterprise_mode: bool = False
    max_users_per_org: int = 500

    # ── Knowledge Packaging ───────────────────────────────────────────────────
    pack_schema_version: str = "1.0"
    max_pack_size_mb: int = 50

    @classmethod
    def from_env(cls) -> "Settings":
        values: dict = {}
        for field_name in cls.model_fields:
            env_name = f"FIXFINDER_{field_name.upper()}"
            if env_name in os.environ:
                values[field_name] = os.environ[env_name]
        return cls(**values)


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()


settings = get_settings()
