from __future__ import annotations

from datetime import datetime, timedelta, timezone
import asyncio
import logging
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response, status
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import case, delete, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from weasyprint import HTML

from app.core.config import settings
from app.core.security import require_admin_auth, require_ingest_token
from app.db.models import GpsPoint, Run, TelemetrySample
from app.db.session import get_session
from app.schemas import (
    AdminSessionRequest,
    AuthSessionStatus,
    GpsResponse,
    IngestRequest,
    RunStartRequest,
    RunStartResponse,
    RunStopResponse,
    RunSummary,
    TelemetryResponse,
)
from app.services.ingest_queue import IngestEvent, build_gps_row, build_telemetry_row


router = APIRouter(prefix="/api/v1")
logger = logging.getLogger(__name__)
TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
TEMPLATE_ENV = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)
REPORT_CACHE: dict[UUID, tuple[bytes, str]] = {}
REPORT_CACHE_MAX_SIZE = 32


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


def _invalidate_report_cache(run_id: UUID) -> None:
    REPORT_CACHE.pop(run_id, None)


def _remember_report(run_id: UUID, pdf_bytes: bytes, filename: str) -> None:
    REPORT_CACHE[run_id] = (pdf_bytes, filename)
    if len(REPORT_CACHE) > REPORT_CACHE_MAX_SIZE:
        oldest = next(iter(REPORT_CACHE))
        REPORT_CACHE.pop(oldest, None)


def _build_gps_overview_svg(points: list[tuple[float, float]]) -> str:
    width = 720
    height = 320
    pad = 24
    if not points:
        return ""

    lons = [lon for lon, _ in points]
    lats = [lat for _, lat in points]
    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)
    lon_span = max(max_lon - min_lon, 1e-9)
    lat_span = max(max_lat - min_lat, 1e-9)
    scale = min((width - 2 * pad) / lon_span, (height - 2 * pad) / lat_span)
    draw_width = lon_span * scale
    draw_height = lat_span * scale
    offset_x = (width - draw_width) / 2
    offset_y = (height - draw_height) / 2

    def project(lon: float, lat: float) -> tuple[float, float]:
        x = offset_x + (lon - min_lon) * scale
        y = height - (offset_y + (lat - min_lat) * scale)
        return x, y

    projected = [project(lon, lat) for lon, lat in points]
    polyline = " ".join(f"{x:.2f},{y:.2f}" for x, y in projected)
    stride = max(len(projected) // 1200, 1)
    circles = "\n".join(
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="1.5" fill="#dc2626" fill-opacity="0.78" />'
        for x, y in projected[::stride]
    )
    start_x, start_y = projected[0]
    end_x, end_y = projected[-1]
    return f"""
    <svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <pattern id="grid" width="36" height="36" patternUnits="userSpaceOnUse">
          <path d="M 36 0 L 0 0 0 36" fill="none" stroke="#e5e7eb" stroke-width="1"/>
        </pattern>
      </defs>
      <rect x="0" y="0" width="{width}" height="{height}" fill="#f8fafc" stroke="#cbd5e1"/>
      <rect x="0" y="0" width="{width}" height="{height}" fill="url(#grid)"/>
      <polyline fill="none" stroke="#2563eb" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" points="{polyline}" />
      {circles}
      <circle cx="{start_x:.2f}" cy="{start_y:.2f}" r="5.5" fill="#16a34a" stroke="#ffffff" stroke-width="2"/>
      <circle cx="{end_x:.2f}" cy="{end_y:.2f}" r="5.5" fill="#dc2626" stroke="#ffffff" stroke-width="2"/>
      <text x="{start_x + 10:.2f}" y="{start_y - 10:.2f}" font-size="12" fill="#166534">起点</text>
      <text x="{end_x + 10:.2f}" y="{end_y - 10:.2f}" font-size="12" fill="#991b1b">终点</text>
    </svg>
    """.strip()


def _build_baidu_static_map_url(points: list[tuple[float, float]]) -> str:
    if not points or not settings.baidu_map_ak:
        return ""

    stride = max(len(points) // 80, 1)
    sampled = points[::stride]
    start_lon, start_lat = points[0]
    end_lon, end_lat = points[-1]
    min_lon = min(lon for lon, _ in points)
    max_lon = max(lon for lon, _ in points)
    min_lat = min(lat for _, lat in points)
    max_lat = max(lat for _, lat in points)
    center_lon = (min_lon + max_lon) / 2
    center_lat = (min_lat + max_lat) / 2
    path = ";".join(f"{lon:.6f},{lat:.6f}" for lon, lat in sampled)
    markers = f"{start_lon:.6f},{start_lat:.6f}|{end_lon:.6f},{end_lat:.6f}"
    return (
        "https://api.map.baidu.com/staticimage/v2"
        f"?ak={settings.baidu_map_ak}"
        "&width=960&height=360&zoom=15&scale=2"
        f"&center={center_lon:.6f},{center_lat:.6f}"
        f"&markers={markers}"
        "&markerStyles=l,A,0x16a34a|l,B,0xdc2626"
        f"&paths={path}"
        "&pathStyles=0x2563eb,6,0.9"
    )


async def _get_active_run_id(session: AsyncSession) -> Optional[UUID]:
    stmt = (
        select(Run.id)
        .where(Run.ended_at.is_(None))
        .order_by(Run.started_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def _set_admin_session_cookie(response: Response) -> None:
    response.set_cookie(
        key=settings.admin_session_cookie_name,
        value=settings.admin_token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        max_age=60 * 60 * 8,
        path="/",
    )


@router.get("/auth/session", response_model=AuthSessionStatus)
async def auth_session_status(request: Request) -> AuthSessionStatus:
    token = request.cookies.get(settings.admin_session_cookie_name)
    return AuthSessionStatus(authenticated=bool(token and token == settings.admin_token))


@router.post("/auth/session", response_model=AuthSessionStatus)
async def create_auth_session(payload: AdminSessionRequest, response: Response) -> AuthSessionStatus:
    if payload.token != settings.admin_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin token")
    _set_admin_session_cookie(response)
    return AuthSessionStatus(authenticated=True)


@router.delete("/auth/session", response_model=AuthSessionStatus)
async def clear_auth_session(response: Response) -> AuthSessionStatus:
    response.delete_cookie(key=settings.admin_session_cookie_name, path="/")
    return AuthSessionStatus(authenticated=False)


@router.post("/runs/start", response_model=RunStartResponse)
async def start_run(
    payload: Optional[RunStartRequest] = Body(default=None),
    session: AsyncSession = Depends(get_session),
    _auth: None = Depends(require_admin_auth),
):
    _ = payload
    existing_run_id = await _get_active_run_id(session)
    if existing_run_id:
        # 返回现有活跃任务
        stmt = select(Run).where(Run.id == existing_run_id)
        result = await session.execute(stmt)
        existing_run = result.scalar_one()
        logger.info("Active run already exists, returning run_id=%s", existing_run_id)
        return RunStartResponse(
            run_id=existing_run.id,
            run_name=existing_run.run_name,
            started_at=existing_run.started_at
        )

    # 创建新任务
    now = datetime.now(timezone.utc)
    run = Run(
        run_name=f"Run {now.strftime('%Y%m%d-%H%M%S')}",
        started_at=now,
    )
    session.add(run)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing_run_id = await _get_active_run_id(session)
        if not existing_run_id:
            raise HTTPException(status_code=409, detail="Active run already exists")
        result = await session.execute(select(Run).where(Run.id == existing_run_id))
        existing_run = result.scalar_one()
        return RunStartResponse(
            run_id=existing_run.id,
            run_name=existing_run.run_name,
            started_at=existing_run.started_at,
        )
    await session.refresh(run)
    logger.info("Created new run, run_id=%s", run.id)
    return RunStartResponse(run_id=run.id, run_name=run.run_name, started_at=run.started_at)


@router.post("/runs/{run_id}/stop", response_model=RunStopResponse)
async def stop_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    _auth: None = Depends(require_admin_auth),
):
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
    _invalidate_report_cache(run_id)
    return RunStopResponse(run_id=run_id, ended_at=now)


@router.get("/runs", response_model=list[RunSummary])
async def list_runs(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0, le=100000),
    session: AsyncSession = Depends(get_session),
    _auth: None = Depends(require_admin_auth),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = select(Run).where(Run.started_at >= cutoff)
    stmt = stmt.order_by(Run.started_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    runs = result.scalars().all()
    return [
        RunSummary(
            run_id=run.id,
            run_name=run.run_name,
            started_at=run.started_at,
            ended_at=run.ended_at,
        )
        for run in runs
    ]


@router.get("/runs/{run_id}", response_model=RunSummary)
async def get_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    _auth: None = Depends(require_admin_auth),
):
    """获取单个任务的详情"""
    stmt = select(Run).where(Run.id == run_id)
    result = await session.execute(stmt)
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunSummary(
        run_id=run.id,
        run_name=run.run_name,
        started_at=run.started_at,
        ended_at=run.ended_at,
    )


@router.delete("/runs/{run_id}", status_code=204)
async def delete_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    _auth: None = Depends(require_admin_auth),
):
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
    _invalidate_report_cache(run_id)
    return None


@router.get("/runs/{run_id}/gps", response_model=list[GpsResponse])
async def get_gps_points(
    run_id: UUID,
    limit: int = Query(100000, ge=1, le=200000),
    target_points: Optional[int] = Query(None, ge=100, le=50000),
    session: AsyncSession = Depends(get_session),
    _auth: None = Depends(require_admin_auth),
):
    effective_target = min(target_points or settings.gps_map_target_points, limit)
    total_points = (
        await session.execute(select(func.count()).select_from(GpsPoint).where(GpsPoint.run_id == run_id))
    ).scalar_one()
    if total_points == 0:
        return []

    stride = max((total_points + effective_target - 1) // effective_target, 1)
    ranked = (
        select(
            GpsPoint.ts.label("ts"),
            GpsPoint.lon.label("lon"),
            GpsPoint.lat.label("lat"),
            func.row_number().over(order_by=GpsPoint.ts).label("rn"),
        )
        .where(GpsPoint.run_id == run_id)
        .subquery()
    )
    stmt = (
        select(ranked.c.ts, ranked.c.lon, ranked.c.lat)
        .where((ranked.c.rn - 1) % stride == 0)
        .order_by(ranked.c.ts)
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [GpsResponse(ts=row.ts, lon=row.lon, lat=row.lat) for row in rows]


@router.get("/runs/{run_id}/telemetry", response_model=list[TelemetryResponse])
async def get_telemetry(
    run_id: UUID,
    from_ts: Optional[datetime] = Query(None, alias="from"),
    to_ts: Optional[datetime] = Query(None, alias="to"),
    bucket: str = Query("5s"),
    session: AsyncSession = Depends(get_session),
    _auth: None = Depends(require_admin_auth),
):
    bucket_seconds = max(_parse_bucket(bucket), 1)
    ts_bucket = func.time_bucket(text(f"INTERVAL '{bucket_seconds} seconds'"), TelemetrySample.ts).label("ts")

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
    except SQLAlchemyError as exc:
        logger.exception("Telemetry query failed for run_id=%s", run_id)
        raise HTTPException(status_code=500, detail="Telemetry query failed") from exc


@router.get("/runs/{run_id}/report.pdf")
async def get_report_pdf(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    _auth: None = Depends(require_admin_auth),
):
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
    gps_all_stmt = select(GpsPoint.lon, GpsPoint.lat).where(GpsPoint.run_id == run_id).order_by(GpsPoint.ts.asc())
    gps_all_rows = (await session.execute(gps_all_stmt)).all()
    gps_points = [(row.lon, row.lat) for row in gps_all_rows]
    gps_svg = _build_gps_overview_svg(gps_points)
    gps_map_url = _build_baidu_static_map_url(gps_points)

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
    trend_y_ticks: list[dict[str, float | str]] = []
    trend_x_ticks: list[dict[str, float | str]] = []
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

        tick_count = 5
        for tick in range(tick_count + 1):
            value = min_val + (max_val - min_val) * tick / tick_count
            y = height - pad - (height - 2 * pad) * tick / tick_count
            trend_y_ticks.append({"label": f"{value:.0f}", "y": y})

        x_tick_count = min(5, max(len(trend_rows) - 1, 1))
        for tick in range(x_tick_count + 1):
            index = round((len(trend_rows) - 1) * tick / max(x_tick_count, 1))
            x = pad + index * x_step
            trend_x_ticks.append(
                {
                    "label": trend_rows[index].ts.astimezone(timezone.utc).strftime("%H:%M:%S"),
                    "x": x,
                }
            )

    data = {
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
        "gps_map_url": gps_map_url,
        "gps_svg": gps_svg,
        "trend_series": trend_series,
        "trend_y_ticks": trend_y_ticks,
        "trend_x_ticks": trend_x_ticks,
    }

    template = TEMPLATE_ENV.get_template("report.html")
    filename = run.run_name.replace("/", "-") if run.run_name else "report"
    html = template.render(**data)
    pdf_bytes = await asyncio.to_thread(
        lambda: HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf()
    )
    _remember_report(run_id, pdf_bytes, filename)
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}.pdf"'
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@router.post("/ingest", status_code=202)
async def ingest_data(
    payload: IngestRequest,
    session: AsyncSession = Depends(get_session),
    _auth: None = Depends(require_ingest_token),
):
    run_id = await _get_active_run_id(session)
    if run_id is None:
        raise HTTPException(status_code=409, detail="No active run")
    _invalidate_report_cache(run_id)

    # 更新任务的最后数据时间
    now = datetime.now(timezone.utc)
    await session.execute(
        update(Run)
        .where(Run.id == run_id)
        .values(last_data_at=now)
    )
    await session.commit()

    logger.debug("Received ingest payload for run_id=%s", run_id)

    telemetry_row = None
    gps_row = None

    if payload.telemetry:
        telemetry_row = build_telemetry_row(run_id, payload.ts, payload.telemetry.model_dump())

    if payload.gps:
        gps_row = build_gps_row(run_id, payload.ts, payload.gps.model_dump())

    event = IngestEvent(run_id=run_id, ts=payload.ts, telemetry=telemetry_row, gps=gps_row)
    await router.ingest_queue.enqueue(event)
    return {"status": "queued"}
