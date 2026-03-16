from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Literal["development", "staging", "production"] = "development"
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/seed_monitor"
    admin_token: str = "dev-admin-token"
    ingest_token: str = "devtoken"
    admin_session_cookie_name: str = "rsr_admin_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    db_batch_max_size: int = Field(default=500, ge=1, le=10_000)
    db_batch_max_latency_ms: int = Field(default=500, ge=10, le=60_000)
    queue_high_watermark: int = Field(default=2000, ge=1)
    telemetry_push_hz: float = Field(default=5.0, gt=0, le=60)
    gps_push_hz: float = Field(default=1.0, gt=0, le=10)
    retention_days: int = Field(default=30, ge=1, le=365)
    cors_allow_origins: str = "http://localhost:5174,http://127.0.0.1:5174"
    log_level: str = "INFO"
    dead_letter_path: str = "/tmp/rsr-ingest-deadletter.jsonl"
    gps_map_target_points: int = Field(default=3000, ge=100, le=50_000)
    telemetry_history_bucket_seconds: int = Field(default=5, ge=1, le=3600)
    baidu_map_ak: str = ""

    @property
    def cors_allow_origins_list(self) -> list[str]:
        return [item.strip() for item in self.cors_allow_origins.split(",") if item.strip()]

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _normalize_cors(cls, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return ",".join(str(item).strip() for item in value if str(item).strip())
        raise ValueError("CORS_ALLOW_ORIGINS must be a comma separated string or list")

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL must be DEBUG/INFO/WARNING/ERROR/CRITICAL")
        return normalized

    @model_validator(mode="after")
    def _validate_security(self) -> "Settings":
        if self.environment != "development":
            if self.admin_token == "dev-admin-token":
                raise ValueError("ADMIN_TOKEN must be overridden outside development")
            if self.ingest_token == "devtoken":
                raise ValueError("INGEST_TOKEN must be overridden outside development")
            if not self.session_cookie_secure:
                raise ValueError("SESSION_COOKIE_SECURE must be true outside development")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
