from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class RunStartRequest(BaseModel):
    machine_id: str


class RunStartResponse(BaseModel):
    run_id: UUID
    run_name: str
    started_at: datetime


class RunStopResponse(BaseModel):
    run_id: UUID
    ended_at: datetime


class RunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: UUID = Field(alias="id")
    machine_id: str
    run_name: str
    started_at: datetime
    ended_at: Optional[datetime] = None


class TelemetryPayload(BaseModel):
    seed_channels_g: Optional[List[float]] = None
    seed_total_g: Optional[float] = None
    distance_m: Optional[float] = None
    leak_distance_m: Optional[float] = None
    speed_kmh: Optional[float] = None
    alarm_blocked: Optional[bool] = None
    alarm_no_seed: Optional[bool] = None


class GpsPayload(BaseModel):
    lon: float
    lat: float
    alt_m: Optional[float] = None
    heading_deg: Optional[float] = None


class IngestRequest(BaseModel):
    ts: datetime
    machine_id: str
    telemetry: Optional[TelemetryPayload] = None
    gps: Optional[GpsPayload] = None


class TelemetryResponse(BaseModel):
    ts: datetime
    channel1_g: Optional[float] = None
    channel2_g: Optional[float] = None
    channel3_g: Optional[float] = None
    channel4_g: Optional[float] = None
    channel5_g: Optional[float] = None
    seed_total_g: Optional[float] = None
    distance_m: Optional[float] = None
    leak_distance_m: Optional[float] = None
    speed_kmh: Optional[float] = None
    alarm_blocked: Optional[bool] = None
    alarm_no_seed: Optional[bool] = None


class GpsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ts: datetime
    lon: float
    lat: float
    alt_m: Optional[float] = None
    heading_deg: Optional[float] = None
