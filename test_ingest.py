#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RSR 标准联调脚本（管理接口 + ingest 接口）

示例：
  python test_ingest.py
  python test_ingest.py --host localhost --port 8100 --admin-token <ADMIN_TOKEN> --ingest-token <INGEST_TOKEN>
  python test_ingest.py --scheme https --host your.api.host --insecure
  python test_ingest.py --duration 120 --hz 10
"""

from __future__ import annotations

import argparse
import math
import os
import random
import time
from datetime import datetime, timezone
from typing import Any

import requests
from requests import Session
from requests.exceptions import RequestException


def parse_args() -> argparse.Namespace:
    default_host = os.getenv("API_HOST", "localhost")
    default_port = int(os.getenv("API_PORT", "8100"))
    default_scheme = os.getenv("API_SCHEME", "http").strip().lower() or "http"
    default_prefix = os.getenv("API_PREFIX", "/api/v1")

    parser = argparse.ArgumentParser(description="RSR ingest demo client")
    parser.add_argument("--scheme", choices=["http", "https"], default=default_scheme, help="API scheme")
    parser.add_argument("--host", default=default_host, help="API host")
    parser.add_argument("--port", type=int, default=default_port, help="API port")
    parser.add_argument("--api-prefix", default=default_prefix, help="API prefix path")
    parser.add_argument("--admin-token", default=os.getenv("ADMIN_TOKEN", "dev-admin-token"), help="ADMIN_TOKEN")
    parser.add_argument("--ingest-token", default=os.getenv("INGEST_TOKEN", "devtoken"), help="INGEST_TOKEN")
    parser.add_argument("--hz", type=float, default=10.0, help="ingest frequency")
    parser.add_argument("--duration", type=int, default=0, help="seconds, 0=run forever")
    parser.add_argument("--timeout", type=float, default=float(os.getenv("REQUEST_TIMEOUT", "20")), help="request timeout")
    parser.add_argument("--insecure", action="store_true", help="disable TLS cert verification for HTTPS")
    parser.add_argument("--no-auto-stop", action="store_true", help="do not stop run on exit")
    return parser.parse_args()


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def api_base(scheme: str, host: str, port: int, prefix: str) -> str:
    normalized_prefix = prefix if prefix.startswith("/") else f"/{prefix}"
    normalized_prefix = normalized_prefix.rstrip("/")
    return f"{scheme}://{host}:{port}{normalized_prefix}"


def _bearer_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def start_or_get_run(session: Session, base: str, admin_token: str, timeout: float) -> dict[str, Any]:
    resp = session.post(
        f"{base}/runs/start",
        json={},
        headers=_bearer_headers(admin_token),
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def stop_run(session: Session, base: str, run_id: str, admin_token: str, timeout: float) -> None:
    resp = session.post(
        f"{base}/runs/{run_id}/stop",
        headers=_bearer_headers(admin_token),
        timeout=timeout,
    )
    resp.raise_for_status()


def build_payload(step: int, distance_m: float, leak_distance_m: float) -> dict[str, Any]:
    channels = [round(random.uniform(8.0, 12.0), 2) for _ in range(5)]
    seed_total = round(sum(channels), 2)
    speed = round(random.uniform(3.0, 6.0), 2)
    alarm_channels = [1 if random.random() < 0.05 else 0 for _ in range(5)]

    base_lat = 40.0095
    base_lon = 116.3650
    theta = step * 0.05
    lat = round(base_lat + 0.0005 * math.sin(theta) + step * 0.00001, 6)
    lon = round(base_lon + 0.0005 * math.cos(theta * 0.6), 6)

    return {
        "ts": iso_now(),
        "telemetry": {
            "seed_channels_g": channels,
            "seed_total_g": seed_total,
            "distance_m": round(distance_m, 2),
            "leak_distance_m": round(leak_distance_m, 2),
            "speed_kmh": speed,
            "alarm_channels": alarm_channels,
            "alarm_blocked": any(v == 1 for v in alarm_channels),
            "alarm_no_seed": False,
        },
        "gps": {"lon": lon, "lat": lat},
    }


def ingest(session: Session, base: str, ingest_token: str, payload: dict[str, Any], timeout: float) -> tuple[bool, int]:
    resp = session.post(
        f"{base}/ingest",
        headers=_bearer_headers(ingest_token),
        json=payload,
        timeout=timeout,
    )
    return resp.status_code == 202, resp.status_code


def main() -> None:
    args = parse_args()
    base = api_base(args.scheme, args.host, args.port, args.api_prefix)

    print("=" * 60)
    print("RSR test_ingest.py")
    print("=" * 60)
    print(f"API: {base}")
    print(f"HZ : {args.hz}")

    session = requests.Session()
    session.headers.update({"User-Agent": "rsr-test-ingest/1.0"})
    session.verify = not args.insecure

    try:
        run = start_or_get_run(session, base, args.admin_token, args.timeout)
    except RequestException as exc:
        print(f"[ERROR] start run failed: {exc}")
        return

    run_id = run["run_id"]
    print(f"Run ID   : {run_id}")
    print(f"Run Name : {run['run_name']}")

    interval = 1.0 / max(args.hz, 0.1)
    step = 0
    ok = 0
    fail = 0
    distance_m = 0.0
    leak_distance_m = 0.0
    t0 = time.time()

    try:
        while True:
            tick = time.time()

            speed_m_s = random.uniform(3.0, 6.0) / 3.6
            distance_m += speed_m_s * interval
            if random.random() < 0.05:
                leak_distance_m += speed_m_s * interval

            payload = build_payload(step, distance_m, leak_distance_m)
            success, status_code = ingest(session, base, args.ingest_token, payload, args.timeout)
            if success:
                ok += 1
            else:
                fail += 1
                if fail <= 5:
                    print(f"[WARN] ingest failed with status={status_code}")

            step += 1
            if step % int(max(args.hz, 1)) == 0:
                print(
                    f"[STAT] sent={step} ok={ok} fail={fail} "
                    f"dist={distance_m:.1f}m leak={leak_distance_m:.1f}m"
                )

            if args.duration > 0 and (time.time() - t0) >= args.duration:
                break

            spent = time.time() - tick
            if spent < interval:
                time.sleep(interval - spent)

    except KeyboardInterrupt:
        print("\n[INFO] interrupted by user")

    finally:
        if not args.no_auto_stop:
            try:
                stop_run(session, base, run_id, args.admin_token, args.timeout)
                print(f"[INFO] run stopped: {run_id}")
            except Exception as exc:
                print(f"[WARN] failed to stop run: {exc}")
        else:
            print(f"[INFO] keep run active: {run_id}")

        print("=" * 60)
        print(f"total={step}, ok={ok}, fail={fail}")
        print("=" * 60)


if __name__ == "__main__":
    main()