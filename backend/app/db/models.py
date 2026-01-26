from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    machine_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    run_name: Mapped[str] = mapped_column(String(128), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_data_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    telemetry_samples: Mapped[list["TelemetrySample"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    gps_points: Mapped[list["GpsPoint"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class TelemetrySample(Base):
    __tablename__ = "telemetry_samples"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    channel1_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    channel2_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    channel3_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    channel4_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    channel5_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    seed_total_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    leak_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed_kmh: Mapped[float | None] = mapped_column(Float, nullable=True)
    uniformity_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    alarm_blocked: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    alarm_no_seed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    alarm_channel1: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    alarm_channel2: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    alarm_channel3: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    alarm_channel4: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    alarm_channel5: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)

    run: Mapped[Run] = relationship(back_populates="telemetry_samples")


class GpsPoint(Base):
    __tablename__ = "gps_points"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    lon: Mapped[float] = mapped_column(Float, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)

    run: Mapped[Run] = relationship(back_populates="gps_points")


Index("ix_telemetry_run_ts", TelemetrySample.run_id, TelemetrySample.ts)
Index("ix_gps_run_ts", GpsPoint.run_id, GpsPoint.ts)
