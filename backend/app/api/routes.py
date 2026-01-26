from __future__ import annotations

from datetime import datetime, timedelta, timezone
import asyncio
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import case, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from weasyprint import HTML

from app.core.config import settings
from app.db.models import GpsPoint, Run, TelemetrySample
from app.db.session import get_session
from app.schemas import (
    GpsResponse,
    IngestRequest,
    RunStartRequest,
    RunStartResponse,
    RunStopResponse,
    RunSummary,
    TelemetryResponse,
)
from app.services.ingest_queue import (
    Broadcaster,
    IngestEvent,
    build_gps_row,
    build_telemetry_row,
)


router = APIRouter(prefix="/api/v1")
TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
TEMPLATE_ENV = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)
REPORT_CACHE: dict[UUID, tuple[bytes, str]] = {}


def _parse_bucket(bucket: str) -> int:
    if bucket.endswith("s"):
        return int(bucket[:-1])
    if bucket.endswith("m"):
        return int(bucket[:-1]) * 60
    if bucket.endswith("h"):
        return int(bucket[:-1]) * 3600
    return int(bucket)


def _format_dt(value: Optional[datetime]) -> str:
    if not value:
        return "-"
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _safe_float(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "0"
    return f"{value:.{digits}f}"


async def _get_active_run_id(session: AsyncSession, machine_id: str) -> Optional[UUID]:
    stmt = (
        select(Run.id)
        .where(Run.machine_id == machine_id)
        .where(Run.ended_at.is_(None))
        .order_by(Run.started_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


@router.post("/runs/start", response_model=RunStartResponse)
async def start_run(payload: RunStartRequest, session: AsyncSession = Depends(get_session)):
    # 检查是否已有活跃任务（同一 machine_id）
    existing_run_id = await _get_active_run_id(session, payload.machine_id)
    if existing_run_id:
        # 返回现有活跃任务
        stmt = select(Run).where(Run.id == existing_run_id)
        result = await session.execute(stmt)
        existing_run = result.scalar_one()
        print(f"[START] Active run already exists for machine_id: {payload.machine_id}, returning: {existing_run_id}")
        return RunStartResponse(
            run_id=existing_run.id,
            run_name=existing_run.run_name,
            started_at=existing_run.started_at
        )

    # 创建新任务
    now = datetime.now(timezone.utc)
    run = Run(
        machine_id=payload.machine_id,
        run_name=f"Run {payload.machine_id} {now.strftime('%Y%m%d-%H%M%S')}",
        started_at=now,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    print(f"[START] Created new run for machine_id: {payload.machine_id}, run_id: {run.id}")
    return RunStartResponse(run_id=run.id, run_name=run.run_name, started_at=run.started_at)


@router.post("/runs/{run_id}/stop", response_model=RunStopResponse)
async def stop_run(run_id: UUID, session: AsyncSession = Depends(get_session)):
    now = datetime.now(timezone.utc)
    stmt = (
        update(Run)
        .where(Run.id == run_id)
        .values(ended_at=now)
        .returning(Run.id)
    )
    result = await session.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Run not found")
    await session.commit()
    return RunStopResponse(run_id=run_id, ended_at=now)


@router.get("/runs", response_model=list[RunSummary])
async def list_runs(
    days: int = Query(30, ge=1, le=365),
    machine_id: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = select(Run).where(Run.started_at >= cutoff)
    if machine_id:
        stmt = stmt.where(Run.machine_id == machine_id)
    stmt = stmt.order_by(Run.started_at.desc())
    result = await session.execute(stmt)
    runs = result.scalars().all()
    return [
        RunSummary(
            run_id=run.id,
            machine_id=run.machine_id,
            run_name=run.run_name,
            started_at=run.started_at,
            ended_at=run.ended_at,
        )
        for run in runs
    ]


@router.get("/runs/{run_id}", response_model=RunSummary)
async def get_run(run_id: UUID, session: AsyncSession = Depends(get_session)):
    """获取单个任务的详情"""
    stmt = select(Run).where(Run.id == run_id)
    result = await session.execute(stmt)
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunSummary(
        run_id=run.id,
        machine_id=run.machine_id,
        run_name=run.run_name,
        started_at=run.started_at,
        ended_at=run.ended_at,
    )


@router.delete("/runs/{run_id}", status_code=204)
async def delete_run(run_id: UUID, session: AsyncSession = Depends(get_session)):
    """删除指定的播种任务及其关联数据"""
    # 先删除关联的 GPS 点
    await session.execute(delete(GpsPoint).where(GpsPoint.run_id == run_id))
    # 删除关联的遥测数据
    await session.execute(delete(TelemetrySample).where(TelemetrySample.run_id == run_id))
    # 删除任务本身
    result = await session.execute(delete(Run).where(Run.id == run_id))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Run not found")
    await session.commit()
    return None


@router.get("/runs/{run_id}/gps", response_model=list[GpsResponse])
async def get_gps_points(
    run_id: UUID,
    limit: int = Query(100000, ge=1, le=200000),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(GpsPoint).where(GpsPoint.run_id == run_id).order_by(GpsPoint.ts).limit(limit)
    result = await session.execute(stmt)
    points = result.scalars().all()
    return [GpsResponse.model_validate(p) for p in points]


@router.get("/runs/{run_id}/telemetry", response_model=list[TelemetryResponse])
async def get_telemetry(
    run_id: UUID,
    from_ts: Optional[datetime] = Query(None, alias="from"),
    to_ts: Optional[datetime] = Query(None, alias="to"),
    bucket: str = Query("1s"),
    session: AsyncSession = Depends(get_session),
):
    bucket_seconds = max(_parse_bucket(bucket), 1)
    ts_bucket = func.to_timestamp(
        func.floor(func.extract("epoch", TelemetrySample.ts) / bucket_seconds) * bucket_seconds
    ).label("ts")

    stmt = select(
        ts_bucket,
        func.avg(TelemetrySample.channel1_g).label("channel1_g"),
        func.avg(TelemetrySample.channel2_g).label("channel2_g"),
        func.avg(TelemetrySample.channel3_g).label("channel3_g"),
        func.avg(TelemetrySample.channel4_g).label("channel4_g"),
        func.avg(TelemetrySample.channel5_g).label("channel5_g"),
        func.avg(TelemetrySample.seed_total_g).label("seed_total_g"),
        func.avg(TelemetrySample.distance_m).label("distance_m"),
        func.avg(TelemetrySample.leak_distance_m).label("leak_distance_m"),
        func.avg(TelemetrySample.speed_kmh).label("speed_kmh"),
        func.avg(TelemetrySample.uniformity_index).label("uniformity_index"),
        func.bool_or(TelemetrySample.alarm_blocked).label("alarm_blocked"),
        func.bool_or(TelemetrySample.alarm_no_seed).label("alarm_no_seed"),
        func.max(TelemetrySample.alarm_channel1).label("alarm_channel1"),
        func.max(TelemetrySample.alarm_channel2).label("alarm_channel2"),
        func.max(TelemetrySample.alarm_channel3).label("alarm_channel3"),
        func.max(TelemetrySample.alarm_channel4).label("alarm_channel4"),
        func.max(TelemetrySample.alarm_channel5).label("alarm_channel5"),
    ).where(TelemetrySample.run_id == run_id)

    if from_ts:
        stmt = stmt.where(TelemetrySample.ts >= from_ts)
    if to_ts:
        stmt = stmt.where(TelemetrySample.ts <= to_ts)

    stmt = stmt.group_by(ts_bucket).order_by(ts_bucket)

    try:
        result = await session.execute(stmt)
        rows = result.all()
        return [TelemetryResponse(**dict(row._mapping)) for row in rows]
    except Exception as e:
        print(f"Telemetry query error: {e}")
        return []


@router.get("/runs/{run_id}/report.pdf")
async def get_report_pdf(run_id: UUID, session: AsyncSession = Depends(get_session)):
    cached = REPORT_CACHE.get(run_id)
    if cached:
        cached_bytes, cached_name = cached
        headers = {
            "Content-Disposition": f'attachment; filename="{cached_name}.pdf"'
        }
        return Response(content=cached_bytes, media_type="application/pdf", headers=headers)

    run_stmt = select(Run).where(Run.id == run_id)
    run_result = await session.execute(run_stmt)
    run = run_result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    last_stmt = (
        select(TelemetrySample)
        .where(TelemetrySample.run_id == run_id)
        .order_by(TelemetrySample.ts.desc())
        .limit(1)
    )
    last_result = await session.execute(last_stmt)
    last = last_result.scalar_one_or_none()

    trend_stmt = (
        select(
            TelemetrySample.ts,
            TelemetrySample.channel1_g,
            TelemetrySample.channel2_g,
            TelemetrySample.channel3_g,
            TelemetrySample.channel4_g,
            TelemetrySample.channel5_g,
        )
        .where(TelemetrySample.run_id == run_id)
        .order_by(TelemetrySample.ts.desc())
        .limit(120)
    )
    trend_result = await session.execute(trend_stmt)
    trend_rows = list(reversed(trend_result.all()))

    alarm_any_expr = or_(
        TelemetrySample.alarm_blocked.is_(True),
        TelemetrySample.alarm_channel1 > 0,
        TelemetrySample.alarm_channel2 > 0,
        TelemetrySample.alarm_channel3 > 0,
        TelemetrySample.alarm_channel4 > 0,
        TelemetrySample.alarm_channel5 > 0,
    )
    alarm_stmt = select(
        func.coalesce(func.sum(case((alarm_any_expr, 1), else_=0)), 0),
        func.coalesce(func.sum(case((TelemetrySample.alarm_no_seed.is_(True), 1), else_=0)), 0),
    ).where(TelemetrySample.run_id == run_id)
    alarm_result = await session.execute(alarm_stmt)
    alarm_blocked_count, alarm_no_seed_count = alarm_result.one()

    gps_count_stmt = select(func.count()).select_from(GpsPoint).where(GpsPoint.run_id == run_id)
    gps_count = (await session.execute(gps_count_stmt)).scalar_one()

    gps_start_stmt = (
        select(GpsPoint).where(GpsPoint.run_id == run_id).order_by(GpsPoint.ts.asc()).limit(1)
    )
    gps_end_stmt = (
        select(GpsPoint).where(GpsPoint.run_id == run_id).order_by(GpsPoint.ts.desc()).limit(1)
    )
    gps_start = (await session.execute(gps_start_stmt)).scalar_one_or_none()
    gps_end = (await session.execute(gps_end_stmt)).scalar_one_or_none()

    duration_minutes = 0
    if run.ended_at:
        duration_minutes = max(
            int((run.ended_at - run.started_at).total_seconds() // 60),
            0,
        )

    if last:
        channels = [
            last.channel1_g or 0,
            last.channel2_g or 0,
            last.channel3_g or 0,
            last.channel4_g or 0,
            last.channel5_g or 0,
        ]
        total = sum(channels)
        distance = last.distance_m or 0
        uniformity = total / distance if distance > 0 and total > 0 else 0
    else:
        channels = [0, 0, 0, 0, 0]
        uniformity = 0

    trend_series = []
    if trend_rows:
        values = [
            v
            for row in trend_rows
            for v in [row.channel1_g, row.channel2_g, row.channel3_g, row.channel4_g, row.channel5_g]
            if v is not None
        ]
        min_val = min(values) if values else 0
        max_val = max(values) if values else 1
        if max_val - min_val < 1e-6:
            max_val = min_val + 1

        width = 700
        height = 180
        pad = 20
        x_step = (width - 2 * pad) / max(len(trend_rows) - 1, 1)

        def build_points(idx: int) -> str:
            points = []
            for i, row in enumerate(trend_rows):
                val = getattr(row, f"channel{idx}_g") or 0
                ratio = (val - min_val) / (max_val - min_val)
                x = pad + i * x_step
                y = height - pad - ratio * (height - 2 * pad)
                points.append(f"{x:.1f},{y:.1f}")
            return " ".join(points)

        trend_series = [
            {"name": "通道1", "color": "#3b82f6", "points": build_points(1)},
            {"name": "通道2", "color": "#22c55e", "points": build_points(2)},
            {"name": "通道3", "color": "#f97316", "points": build_points(3)},
            {"name": "通道4", "color": "#ef4444", "points": build_points(4)},
            {"name": "通道5", "color": "#a855f7", "points": build_points(5)},
        ]

    data = {
        "machine_id": run.machine_id,
        "run_name": run.run_name,
        "started_at": _format_dt(run.started_at),
        "ended_at": _format_dt(run.ended_at),
        "duration": f"{duration_minutes} 分钟",
        "total_seed_kg": _safe_float((last.seed_total_g / 1000) if last and last.seed_total_g else 0),
        "total_distance_km": _safe_float((last.distance_m / 1000) if last and last.distance_m else 0),
        "leak_distance_km": _safe_float((last.leak_distance_m / 1000) if last and last.leak_distance_m else 0),
        "avg_speed_kmh": _safe_float(last.speed_kmh if last else 0),
        "uniformity_index": _safe_float(uniformity, 2),
        "channel1_kg": _safe_float(channels[0] / 1000),
        "channel2_kg": _safe_float(channels[1] / 1000),
        "channel3_kg": _safe_float(channels[2] / 1000),
        "channel4_kg": _safe_float(channels[3] / 1000),
        "channel5_kg": _safe_float(channels[4] / 1000),
        "alarm_blocked_count": alarm_blocked_count,
        "alarm_no_seed_count": alarm_no_seed_count,
        "gps_point_count": gps_count,
        "start_location": f"{gps_start.lat:.6f}, {gps_start.lon:.6f}" if gps_start else "-",
        "end_location": f"{gps_end.lat:.6f}, {gps_end.lon:.6f}" if gps_end else "-",
        "trend_series": trend_series,
    }

    template = TEMPLATE_ENV.get_template("report.html")
    filename = run.run_name.replace("/", "-") if run.run_name else "report"
    html = template.render(**data)
    pdf_bytes = await asyncio.to_thread(
        lambda: HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf()
    )
    REPORT_CACHE[run_id] = (pdf_bytes, filename)
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}.pdf"'
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@router.post("/ingest", status_code=202)
async def ingest_data(
    payload: IngestRequest,
    authorization: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_session),
    broadcaster: Broadcaster = Depends(lambda: router.broadcaster),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1]
    if token != settings.ingest_token:
        raise HTTPException(status_code=403, detail="Invalid token")

    run_id = await _get_active_run_id(session, payload.machine_id)
    if run_id is None:
        raise HTTPException(status_code=409, detail="No active run")

    # 更新任务的最后数据时间
    now = datetime.now(timezone.utc)
    await session.execute(
        update(Run)
        .where(Run.id == run_id)
        .values(last_data_at=now)
    )
    await session.commit()

    print(f"[INGEST] Received data for machine_id: {payload.machine_id}, run_id: {run_id}")

    telemetry_row = None
    gps_row = None

    if payload.telemetry:
        telemetry_row = build_telemetry_row(run_id, payload.ts, payload.telemetry.model_dump())
        await broadcaster.update_telemetry(run_id, {"ts": payload.ts.isoformat(), **payload.telemetry.model_dump()})

    if payload.gps:
        gps_row = build_gps_row(run_id, payload.ts, payload.gps.model_dump())
        await broadcaster.update_gps(run_id, {"ts": payload.ts.isoformat(), **payload.gps.model_dump()})

    event = IngestEvent(run_id=run_id, ts=payload.ts, telemetry=telemetry_row, gps=gps_row)
    await router.ingest_queue.enqueue(event)
    return {"status": "queued"}
