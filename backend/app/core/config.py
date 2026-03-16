from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name, str(default))
    try:
        return int(value)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name, str(default))
    try:
        return float(value)
    except ValueError:
        return default


def _get_csv(name: str, default: str) -> List[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@db:5432/seed_monitor",
    )
    admin_token: str = os.getenv("ADMIN_TOKEN", "dev-admin-token")
    ingest_token: str = os.getenv("INGEST_TOKEN", "devtoken")
    db_batch_max_size: int = _get_int("DB_BATCH_MAX_SIZE", 500)
    db_batch_max_latency_ms: int = _get_int("DB_BATCH_MAX_LATENCY_MS", 500)
    queue_high_watermark: int = _get_int("QUEUE_HIGH_WATERMARK", 2000)
    telemetry_push_hz: float = _get_float("TELEMETRY_PUSH_HZ", 5.0)
    gps_push_hz: float = _get_float("GPS_PUSH_HZ", 1.0)
    retention_days: int = _get_int("RETENTION_DAYS", 30)
    cors_allow_origins: list[str] = field(
        default_factory=lambda: _get_csv(
            "CORS_ALLOW_ORIGINS",
            "http://localhost:5174,http://127.0.0.1:5174",
        )
    )
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()


settings = Settings()
