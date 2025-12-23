from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete

from app.api import routes
from app.core.config import settings
from app.db.models import Run
from app.db.session import async_session_factory
from app.services.ingest_queue import Broadcaster, IngestQueue

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.cors_allow_origins == "*" else settings.cors_allow_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

broadcaster = Broadcaster()
ingest_queue = IngestQueue(broadcaster)

routes.router.broadcaster = broadcaster
routes.router.ingest_queue = ingest_queue

app.include_router(routes.router)


@app.on_event("startup")
async def startup() -> None:
    app.state.telemetry_task = asyncio.create_task(broadcaster.telemetry_loop())
    app.state.gps_task = asyncio.create_task(broadcaster.gps_loop())
    app.state.worker_task = asyncio.create_task(ingest_queue.worker_loop())
    app.state.retention_task = asyncio.create_task(_retention_loop())


@app.on_event("shutdown")
async def shutdown() -> None:
    for task in [app.state.telemetry_task, app.state.gps_task, app.state.worker_task, app.state.retention_task]:
        task.cancel()


@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket, run_id: str) -> None:
    await websocket.accept()
    try:
        run_uuid = UUID(run_id)
    except ValueError:
        await websocket.close(code=1008)
        return

    await broadcaster.add_client(run_uuid, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await broadcaster.remove_client(run_uuid, websocket)


async def _retention_loop() -> None:
    while True:
        await asyncio.sleep(24 * 60 * 60)
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.retention_days)
        async with async_session_factory() as session:
            await session.execute(delete(Run).where(Run.started_at < cutoff))
            await session.commit()
