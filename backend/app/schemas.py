from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
    run_id: UUID
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
    uniformity_index: Optional[float] = None
    alarm_channels: Optional[List[int]] = None  # 5个通道的警报状态，会转换为 alarm_blocked
    alarm_blocked: Optional[bool] = None
    alarm_no_seed: Optional[bool] = None


class GpsPayload(BaseModel):
    lon: float
    lat: float


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
    uniformity_index: Optional[float] = None
    alarm_blocked: Optional[bool] = None
    alarm_no_seed: Optional[bool] = None
    alarm_channel1: Optional[int] = None
    alarm_channel2: Optional[int] = None
    alarm_channel3: Optional[int] = None
    alarm_channel4: Optional[int] = None
    alarm_channel5: Optional[int] = None


class GpsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ts: datetime
    lon: float
    lat: float
