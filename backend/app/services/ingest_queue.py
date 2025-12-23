from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import insert

from app.core.config import settings
from app.db.models import GpsPoint, TelemetrySample
from app.db.session import async_session_factory


@dataclass
class IngestEvent:
    run_id: UUID
    ts: datetime
    telemetry: Optional[Dict[str, Any]] = None
    gps: Optional[Dict[str, Any]] = None


class Broadcaster:
    def __init__(self) -> None:
        self._clients: dict[UUID, set[Any]] = {}
        self._latest_telemetry: dict[UUID, dict[str, Any]] = {}
        self._latest_gps: dict[UUID, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def add_client(self, run_id: UUID, websocket: Any) -> None:
        async with self._lock:
            self._clients.setdefault(run_id, set()).add(websocket)

    async def remove_client(self, run_id: UUID, websocket: Any) -> None:
        async with self._lock:
            clients = self._clients.get(run_id)
            if not clients:
                return
            clients.discard(websocket)
            if not clients:
                self._clients.pop(run_id, None)

    async def update_telemetry(self, run_id: UUID, payload: dict[str, Any]) -> None:
        async with self._lock:
            self._latest_telemetry[run_id] = payload

    async def update_gps(self, run_id: UUID, payload: dict[str, Any]) -> None:
        async with self._lock:
            self._latest_gps[run_id] = payload

    async def _broadcast(self, run_id: UUID, message: dict[str, Any]) -> None:
        clients = self._clients.get(run_id, set())
        if not clients:
            return
        stale = []
        for client in list(clients):
            try:
                await client.send_json(message)
            except Exception:
                stale.append(client)
        if stale:
            for client in stale:
                clients.discard(client)

    async def telemetry_loop(self) -> None:
        interval = 1.0 / max(settings.telemetry_push_hz, 0.1)
        while True:
            await asyncio.sleep(interval)
            async with self._lock:
                items = list(self._latest_telemetry.items())
            for run_id, payload in items:
                await self._broadcast(run_id, {"type": "telemetry", "data": payload})

    async def gps_loop(self) -> None:
        interval = 1.0 / max(settings.gps_push_hz, 0.1)
        while True:
            await asyncio.sleep(interval)
            async with self._lock:
                items = list(self._latest_gps.items())
            for run_id, payload in items:
                await self._broadcast(run_id, {"type": "gps", "data": payload})


class IngestQueue:
    def __init__(self, broadcaster: Broadcaster) -> None:
        self._queue: asyncio.Queue[IngestEvent] = asyncio.Queue()
        self._broadcaster = broadcaster

    @property
    def queue(self) -> asyncio.Queue[IngestEvent]:
        return self._queue

    async def enqueue(self, event: IngestEvent) -> None:
        await self._queue.put(event)

    async def worker_loop(self) -> None:
        batch_telemetry: list[dict[str, Any]] = []
        batch_gps: list[dict[str, Any]] = []
        batch_max = settings.db_batch_max_size
        batch_latency = settings.db_batch_max_latency_ms / 1000.0
        last_flush = time.monotonic()

        telemetry_latest: dict[UUID, dict[str, Any]] = {}
        gps_latest: dict[tuple[UUID, datetime], dict[str, Any]] = {}

        while True:
            timeout = max(batch_latency - (time.monotonic() - last_flush), 0.0)
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=timeout)
                backpressure = self._queue.qsize() > settings.queue_high_watermark
                if backpressure:
                    if event.telemetry:
                        telemetry_latest[event.run_id] = event.telemetry
                    if event.gps:
                        second_ts = event.ts.replace(microsecond=0, tzinfo=timezone.utc)
                        gps_latest[(event.run_id, second_ts)] = event.gps
                else:
                    if event.telemetry:
                        batch_telemetry.append(event.telemetry)
                    if event.gps:
                        batch_gps.append(event.gps)
            except asyncio.TimeoutError:
                pass

            now = time.monotonic()
            if now - last_flush >= batch_latency or len(batch_telemetry) + len(batch_gps) >= batch_max:
                if telemetry_latest:
                    batch_telemetry.extend(telemetry_latest.values())
                    telemetry_latest.clear()
                if gps_latest:
                    batch_gps.extend(gps_latest.values())
                    gps_latest.clear()

                if batch_telemetry or batch_gps:
                    await self._flush(batch_telemetry, batch_gps)
                    batch_telemetry.clear()
                    batch_gps.clear()
                last_flush = time.monotonic()

    async def _flush(self, telemetry_rows: list[dict[str, Any]], gps_rows: list[dict[str, Any]]) -> None:
        async with async_session_factory() as session:
            if telemetry_rows:
                await session.execute(insert(TelemetrySample), telemetry_rows)
            if gps_rows:
                await session.execute(insert(GpsPoint), gps_rows)
            await session.commit()


def build_telemetry_row(run_id: UUID, ts: datetime, telemetry: dict[str, Any]) -> dict[str, Any]:
    channels = telemetry.get("seed_channels_g") or []
    padded = list(channels) + [None] * (5 - len(channels))
    return {
        "run_id": run_id,
        "ts": ts,
        "channel1_g": padded[0],
        "channel2_g": padded[1],
        "channel3_g": padded[2],
        "channel4_g": padded[3],
        "channel5_g": padded[4],
        "seed_total_g": telemetry.get("seed_total_g"),
        "distance_m": telemetry.get("distance_m"),
        "leak_distance_m": telemetry.get("leak_distance_m"),
        "speed_kmh": telemetry.get("speed_kmh"),
        "alarm_blocked": telemetry.get("alarm_blocked"),
        "alarm_no_seed": telemetry.get("alarm_no_seed"),
    }


def build_gps_row(run_id: UUID, ts: datetime, gps: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "ts": ts,
        "lon": gps.get("lon"),
        "lat": gps.get("lat"),
        "alt_m": gps.get("alt_m"),
        "heading_deg": gps.get("heading_deg"),
    }
