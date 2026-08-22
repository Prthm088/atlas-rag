from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(Path(__file__).parents[2] / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "Atlas API"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"

    database_url: str | None = None
    database_pool_size: int = Field(default=5, ge=1, le=20)
    database_max_overflow: int = Field(default=5, ge=0, le=20)

    supabase_url: str | None = None
    supabase_publishable_key: str | None = None
    supabase_service_role_key: str | None = None
    supabase_storage_bucket: str = "documents"
    supabase_jwt_audience: str = "authenticated"
    auth_verify_mode: Literal["jwks", "remote"] = "jwks"

    gemini_api_key: str | None = None
    gemini_chat_model: str = "gemini-3.6-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = Field(default=768, ge=128, le=4096)

    cors_origins: str = "http://localhost:3000"
    trusted_hosts: str = "localhost,127.0.0.1"
    max_file_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    max_documents_per_user: int = Field(default=5, ge=1, le=100)
    max_storage_bytes_per_user: int = Field(default=50 * 1024 * 1024, ge=1024)
    max_pdf_pages: int = Field(default=200, ge=1, le=2000)
    max_chunks_per_document: int = Field(default=1200, ge=1, le=10000)
    chat_requests_per_minute: int = Field(default=12, ge=1, le=1000)
    uploads_per_hour: int = Field(default=10, ge=1, le=1000)

    job_poll_seconds: float = Field(default=2.0, ge=0.25, le=60)
    job_max_attempts: int = Field(default=3, ge=1, le=10)
    conversation_recent_messages: int = Field(default=12, ge=2, le=50)
    conversation_summary_trigger: int = Field(default=18, ge=4, le=200)
    retrieval_vector_limit: int = Field(default=30, ge=1, le=100)
    retrieval_keyword_limit: int = Field(default=30, ge=1, le=100)
    retrieval_final_limit: int = Field(default=8, ge=1, le=30)

    storage_backend: Literal["supabase", "filesystem"] = "supabase"
    local_storage_path: Path = Path(".data/storage")

    @field_validator("api_v1_prefix")
    @classmethod
    def normalize_prefix(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith("/"):
            value = f"/{value}"
        return value.rstrip("/")

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip().rstrip("/") for item in self.cors_origins.split(",") if item.strip()]

    @property
    def trusted_host_list(self) -> list[str]:
        return [item.strip() for item in self.trusted_hosts.split(",") if item.strip()]

    @property
    def jwks_url(self) -> str | None:
        if not self.supabase_url:
            return None
        return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"

    @property
    def auth_issuer(self) -> str | None:
        if not self.supabase_url:
            return None
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    def missing_runtime_configuration(self) -> list[str]:
        required = {
            "DATABASE_URL": self.database_url,
            "SUPABASE_URL": self.supabase_url,
            "SUPABASE_PUBLISHABLE_KEY": self.supabase_publishable_key,
            "SUPABASE_SERVICE_ROLE_KEY": self.supabase_service_role_key,
            "GEMINI_API_KEY": self.gemini_api_key,
        }
        if self.storage_backend == "filesystem":
            required.pop("SUPABASE_SERVICE_ROLE_KEY")
        return [name for name, value in required.items() if not value]


@lru_cache
def get_settings() -> Settings:
    return Settings()
