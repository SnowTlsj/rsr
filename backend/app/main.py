from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete, select, text, update

from app.api import routes
from app.core.config import settings
from app.core.security import websocket_require_admin_session
from app.db.models import Run
from app.db.session import async_session_factory
from app.services.ingest_queue import Broadcaster, IngestQueue


logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

broadcaster = Broadcaster()
ingest_queue = IngestQueue(broadcaster)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup")
    routes.router.broadcaster = broadcaster
    routes.router.ingest_queue = ingest_queue
    tasks = [
        asyncio.create_task(broadcaster.telemetry_loop(), name="telemetry_loop"),
        asyncio.create_task(broadcaster.gps_loop(), name="gps_loop"),
        asyncio.create_task(ingest_queue.worker_loop(), name="ingest_worker"),
        asyncio.create_task(_retention_loop(), name="retention_loop"),
        asyncio.create_task(_timeout_check_loop(), name="timeout_loop"),
    ]
    app.state.background_tasks = tasks
    try:
        yield
    finally:
        logger.info("Application shutdown")
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:
        logger.exception("Readiness check failed: %s", exc)
        raise HTTPException(status_code=503, detail="Database not ready") from exc


@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket, run_id: str) -> None:
    await websocket_require_admin_session(websocket)
    await websocket.accept()

    try:
        run_uuid = UUID(run_id)
    except ValueError:
        await websocket.close(code=1008)
        return

    await broadcaster.add_client(run_uuid, websocket)
    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=70)
            except asyncio.TimeoutError:
                await websocket.close(code=1001)
                break
    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected for run_id=%s", run_uuid)
    finally:
        await broadcaster.remove_client(run_uuid, websocket)


async def _retention_loop() -> None:
    while True:
        await asyncio.sleep(24 * 60 * 60)
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.retention_days)
        async with async_session_factory() as session:
            await session.execute(delete(Run).where(Run.started_at < cutoff))
            await session.commit()
        logger.info("Retention cleanup complete, cutoff=%s", cutoff.isoformat())


async def _timeout_check_loop() -> None:
    while True:
        await asyncio.sleep(30)
        now = datetime.now(timezone.utc)
        timeout_threshold = now - timedelta(minutes=3)

        async with async_session_factory() as session:
            stmt = select(Run).where(Run.ended_at.is_(None))
            result = await session.execute(stmt)
            active_runs = result.scalars().all()

            for run in active_runs:
                if run.last_data_at and run.last_data_at < timeout_threshold:
                    logger.warning(
                        "Auto-stopping run %s due to inactivity (last_data_at=%s)",
                        run.id,
                        run.last_data_at,
                    )
                    await session.execute(
                        update(Run)
                        .where(Run.id == run.id)
                        .values(ended_at=now)
                    )
                    await session.commit()
                elif not run.last_data_at and run.started_at < timeout_threshold:
                    logger.warning(
                        "Auto-stopping run %s due to no data received (started_at=%s)",
                        run.id,
                        run.started_at,
                    )
                    await session.execute(
                        update(Run)
                        .where(Run.id == run.id)
                        .values(ended_at=now)
                    )
                    await session.commit()
