from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete, update

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
    app.state.timeout_task = asyncio.create_task(_timeout_check_loop())


@app.on_event("shutdown")
async def shutdown() -> None:
    for task in [
        app.state.telemetry_task,
        app.state.gps_task,
        app.state.worker_task,
        app.state.retention_task,
        app.state.timeout_task,
    ]:
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
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=70)
            except asyncio.TimeoutError:
                await websocket.close(code=1001)
                break
    except WebSocketDisconnect:
        pass
    finally:
        await broadcaster.remove_client(run_uuid, websocket)


async def _retention_loop() -> None:
    while True:
        await asyncio.sleep(24 * 60 * 60)
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.retention_days)
        async with async_session_factory() as session:
            await session.execute(delete(Run).where(Run.started_at < cutoff))
            await session.commit()


async def _timeout_check_loop() -> None:
    """定期检查活跃任务，如果超过3分钟没有数据输入，自动终止任务"""
    while True:
        await asyncio.sleep(30)  # 每30秒检查一次
        now = datetime.now(timezone.utc)
        timeout_threshold = now - timedelta(minutes=3)

        async with async_session_factory() as session:
            # 查找所有活跃任务
            from sqlalchemy import select
            stmt = select(Run).where(Run.ended_at.is_(None))
            result = await session.execute(stmt)
            active_runs = result.scalars().all()

            for run in active_runs:
                # 如果任务有 last_data_at 且超过3分钟没有数据
                if run.last_data_at and run.last_data_at < timeout_threshold:
                    print(f"[TIMEOUT] Auto-stopping run {run.id} due to inactivity (last data: {run.last_data_at})")
                    await session.execute(
                        update(Run)
                        .where(Run.id == run.id)
                        .values(ended_at=now)
                    )
                    await session.commit()
                # 如果任务从未收到数据，且启动时间超过3分钟
                elif not run.last_data_at and run.started_at < timeout_threshold:
                    print(f"[TIMEOUT] Auto-stopping run {run.id} due to no data received (started: {run.started_at})")
                    await session.execute(
                        update(Run)
                        .where(Run.id == run.id)
                        .values(ended_at=now)
                    )
                    await session.commit()
