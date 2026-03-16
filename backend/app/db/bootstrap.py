from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings


DDL = [
    """
    CREATE TABLE IF NOT EXISTS runs (
        id UUID PRIMARY KEY,
        run_name VARCHAR(128) NOT NULL,
        started_at TIMESTAMPTZ NOT NULL,
        ended_at TIMESTAMPTZ NULL,
        last_data_at TIMESTAMPTZ NULL,
        notes TEXT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS telemetry_samples (
        id BIGSERIAL PRIMARY KEY,
        run_id UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
        ts TIMESTAMPTZ NOT NULL,
        channel1_g DOUBLE PRECISION NULL,
        channel2_g DOUBLE PRECISION NULL,
        channel3_g DOUBLE PRECISION NULL,
        channel4_g DOUBLE PRECISION NULL,
        channel5_g DOUBLE PRECISION NULL,
        seed_total_g DOUBLE PRECISION NULL,
        distance_m DOUBLE PRECISION NULL,
        leak_distance_m DOUBLE PRECISION NULL,
        speed_kmh DOUBLE PRECISION NULL,
        uniformity_index DOUBLE PRECISION NULL,
        alarm_blocked BOOLEAN NULL,
        alarm_no_seed BOOLEAN NULL,
        alarm_channel1 INTEGER NULL,
        alarm_channel2 INTEGER NULL,
        alarm_channel3 INTEGER NULL,
        alarm_channel4 INTEGER NULL,
        alarm_channel5 INTEGER NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS gps_points (
        id BIGSERIAL PRIMARY KEY,
        run_id UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
        ts TIMESTAMPTZ NOT NULL,
        lon DOUBLE PRECISION NOT NULL,
        lat DOUBLE PRECISION NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_telemetry_run_ts ON telemetry_samples(run_id, ts)",
    "CREATE INDEX IF NOT EXISTS ix_gps_run_ts ON gps_points(run_id, ts)",
]


async def bootstrap() -> None:
    engine = create_async_engine(settings.database_url, future=True, pool_pre_ping=True)
    try:
        async with engine.begin() as conn:
            for stmt in DDL:
                await conn.execute(text(stmt))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(bootstrap())
