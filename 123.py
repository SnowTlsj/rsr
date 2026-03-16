#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Serial -> RSR ingest bridge

Purpose:
1. Auto-detect Windows/Linux runtime.
2. Auto-discover likely serial ports.
3. Monitor serial data continuously.
4. When valid payload is detected, automatically create/start a run.
5. Normalize serial array data into the backend ingest JSON format.
6. Upload telemetry/GPS to the cloud API.

Dependencies:
  pip install pyserial requests

Notes:
- The serial array protocol is not final yet. Update `ARRAY_MAPPING` or
  `build_payload_from_array()` after you provide the real device format.
- Cloud configuration is intentionally placed at the top of this file.
"""

from __future__ import annotations

import json
import platform
import queue
import re
import signal
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import serial
from requests import Session
from requests.exceptions import RequestException
from serial.tools import list_ports


# ============================================================================
# Cloud config
# ============================================================================
# 云端接口协议，通常保持 http；如果以后上 HTTPS 再改成 https。
API_SCHEME = "http"
# 云服务器域名或 IP。
API_HOST = "nas.tlsi.top"
# 后端 API 对外端口。
API_PORT = 8100
# 后端接口统一前缀。
API_PREFIX = "/api/v1"

# 管理令牌，用于自动开始/停止任务。
ADMIN_TOKEN = "snowtlsj"
# 数据上传令牌，用于 /ingest 写入。
INGEST_TOKEN = "snowtlsj"

# 单次 HTTP 请求超时时间，单位秒。
REQUEST_TIMEOUT = 15
# 是否校验证书；HTTP 环境一般为 False。
VERIFY_TLS = False


# ============================================================================
# Serial config
# ============================================================================
# 串口波特率，需与单片机固件一致。
SERIAL_BAUDRATE = 115200
# 串口读超时，单位秒。
SERIAL_TIMEOUT = 0.5
# 串口异常断开后，重新尝试前的等待时间。
SERIAL_REOPEN_DELAY_SEC = 2.0
# 扫描可用串口的间隔时间。
SERIAL_SCAN_INTERVAL_SEC = 3.0
# 连续收到多少帧有效数据后，才自动开始任务。
SERIAL_STABLE_LINE_COUNT = 3
# 当前任务在多久没有收到有效数据后，自动判定为结束，单位秒。
RUN_IDLE_STOP_SEC = 15.0
# 是否启用串口握手探测。
SERIAL_HANDSHAKE_ENABLED = True
# 打开串口后，最多等待多久来判断这个串口是不是目标设备。
SERIAL_HANDSHAKE_TIMEOUT_SEC = 60
# 如果设备需要先发唤醒命令，在这里填写字节串；默认空表示被动等待设备发数。
SERIAL_HANDSHAKE_WRITE = b""
# 上传失败时，本地缓存文件路径。
FAILED_CACHE_PATH = "serial_cache.jsonl"
# 每次最多回放多少条缓存数据，避免一次性阻塞主循环。
CACHE_REPLAY_BATCH_SIZE = 20
# 两次缓存回放之间的最小间隔，单位秒。
CACHE_REPLAY_INTERVAL_SEC = 5.0


# ============================================================================
# Device data rules
# Adjust this part after the real MCU protocol is provided.
# ============================================================================
ARRAY_REGEX = re.compile(r"\[([^\]]+)\]")
NUMBER_REGEX = re.compile(r"-?\d+(?:\.\d+)?")

# Example array mapping:
# [ch1, ch2, ch3, ch4, ch5, total, distance, leak_distance, speed, lon, lat, alarm1, alarm2, alarm3, alarm4, alarm5, alarm_blocked, alarm_no_seed]
ARRAY_MAPPING = {
    "channels": [0, 1, 2, 3, 4],
    "seed_total_g": 5,
    "distance_m": 6,
    "leak_distance_m": 7,
    "speed_kmh": 8,
    "lon": 9,
    "lat": 10,
    "alarm_channels": [11, 12, 13, 14, 15],
    "alarm_blocked": 16,
    "alarm_no_seed": 17,
}

# Minimum array length that counts as a valid frame for auto-start.
MIN_VALID_ARRAY_LENGTH = 11


@dataclass
class CloudConfig:
    scheme: str = API_SCHEME
    host: str = API_HOST
    port: int = API_PORT
    api_prefix: str = API_PREFIX
    admin_token: str = ADMIN_TOKEN
    ingest_token: str = INGEST_TOKEN
    timeout: float = REQUEST_TIMEOUT
    verify_tls: bool = VERIFY_TLS

    @property
    def base_url(self) -> str:
        prefix = self.api_prefix if self.api_prefix.startswith("/") else f"/{self.api_prefix}"
        return f"{self.scheme}://{self.host}:{self.port}{prefix.rstrip('/')}"


@dataclass
class SerialPortCandidate:
    device: str
    description: str
    score: int


class SerialIngestBridge:
    def __init__(self, cloud: CloudConfig) -> None:
        self.cloud = cloud
        self.session = requests.Session()
        self.session.verify = cloud.verify_tls
        self.session.headers.update({"User-Agent": "rsr-serial-bridge/1.0"})

        self.stop_event = threading.Event()
        self.line_queue: queue.Queue[tuple[str, str]] = queue.Queue()

        self.current_run_id: str | None = None
        self.current_port: str | None = None
        self.valid_frame_counter = 0
        self.last_valid_frame_at = 0.0
        self.system_name = platform.system().lower()
        self.serial_handle: serial.Serial | None = None
        self.serial_lock = threading.Lock()
        self.reader_thread: threading.Thread | None = None
        self.cache_lock = threading.Lock()
        self.failed_cache_path = Path(FAILED_CACHE_PATH)
        self.last_cache_replay_at = 0.0

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------
    def _admin_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.cloud.admin_token}",
            "Content-Type": "application/json",
        }

    def _ingest_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.cloud.ingest_token}",
            "Content-Type": "application/json",
        }

    def start_or_get_run(self) -> str:
        response = self.session.post(
            f"{self.cloud.base_url}/runs/start",
            headers=self._admin_headers(),
            json={},
            timeout=self.cloud.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        run_id = payload["run_id"]
        print(f"[INFO] active run: {run_id} ({payload.get('run_name', '-')})")
        self.current_run_id = run_id
        return run_id

    def stop_run(self) -> None:
        if not self.current_run_id:
            return
        try:
            response = self.session.post(
                f"{self.cloud.base_url}/runs/{self.current_run_id}/stop",
                headers=self._admin_headers(),
                timeout=self.cloud.timeout,
            )
            response.raise_for_status()
            print(f"[INFO] run stopped: {self.current_run_id}")
        except Exception as exc:
            print(f"[WARN] failed to stop run: {exc}")
        finally:
            self.current_run_id = None

    def _reset_run_state(self) -> None:
        self.current_run_id = None
        self.valid_frame_counter = 0
        self.last_valid_frame_at = 0.0

    def upload_ingest(self, payload: dict[str, Any]) -> None:
        response = self.session.post(
            f"{self.cloud.base_url}/ingest",
            headers=self._ingest_headers(),
            json=payload,
            timeout=self.cloud.timeout,
        )
        if response.status_code == 202:
            return
        if response.status_code == 409:
            self.current_run_id = None
            raise RuntimeError("no active run on server")
        response.raise_for_status()

    def _cache_failed_payload(self, payload: dict[str, Any], reason: str) -> None:
        record = {
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "payload": payload,
        }
        try:
            with self.cache_lock:
                self.failed_cache_path.parent.mkdir(parents=True, exist_ok=True)
                with self.failed_cache_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            print(f"[WARN] failed to persist local cache: {exc}")

    def _clear_failed_cache(self) -> None:
        try:
            with self.cache_lock:
                if self.failed_cache_path.exists():
                    self.failed_cache_path.unlink()
        except OSError as exc:
            print(f"[WARN] failed to clear local cache: {exc}")

    def _replay_cached_payloads(self, force: bool = False) -> None:
        if not self.failed_cache_path.exists():
            return

        now = time.time()
        if not force and now - self.last_cache_replay_at < CACHE_REPLAY_INTERVAL_SEC:
            return
        self.last_cache_replay_at = now

        try:
            with self.cache_lock:
                lines = self.failed_cache_path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            print(f"[WARN] failed to read local cache: {exc}")
            return

        if not lines:
            return

        remaining: list[str] = []
        replayed = 0
        for line in lines:
            if not line.strip():
                continue
            if replayed >= CACHE_REPLAY_BATCH_SIZE:
                remaining.append(line)
                continue
            try:
                record = json.loads(line)
                payload = record.get("payload")
                if not payload:
                    continue
                self.upload_ingest(payload)
                replayed += 1
            except Exception:
                remaining.append(line)

        try:
            with self.cache_lock:
                if remaining:
                    self.failed_cache_path.write_text("\n".join(remaining) + "\n", encoding="utf-8")
                elif self.failed_cache_path.exists():
                    self.failed_cache_path.unlink()
        except OSError as exc:
            print(f"[WARN] failed to rewrite local cache: {exc}")

        if replayed:
            print(f"[INFO] replayed {replayed} cached payload(s)")

    def _finish_current_run(self, reason: str) -> None:
        if not self.current_run_id:
            return
        run_id = self.current_run_id
        print(f"[INFO] finishing run {run_id}: {reason}")
        self._replay_cached_payloads(force=True)
        self.stop_run()
        self._clear_failed_cache()
        self._reset_run_state()
        print(f"[INFO] bridge returned to waiting state after run {run_id}")

    # ------------------------------------------------------------------
    # Serial discovery
    # ------------------------------------------------------------------
    def list_candidate_ports(self) -> list[SerialPortCandidate]:
        candidates: list[SerialPortCandidate] = []
        keywords = (
            "usb",
            "serial",
            "uart",
            "ch340",
            "cp210",
            "ftdi",
            "ttyusb",
            "ttyacm",
            "com",
        )

        for port in list_ports.comports():
            text = " ".join(
                str(value).lower()
                for value in [port.device, port.description, port.manufacturer, port.product]
                if value
            )
            score = 0
            for keyword in keywords:
                if keyword in text:
                    score += 10
            if "bluetooth" in text:
                score -= 20
            if score <= 0:
                score = 1
            candidates.append(
                SerialPortCandidate(
                    device=port.device,
                    description=port.description or "",
                    score=score,
                )
            )

        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates

    def _open_serial_port(self, port_name: str) -> serial.Serial:
        print(f"[INFO] opening serial port: {port_name} @ {SERIAL_BAUDRATE}")
        ser = serial.Serial()
        ser.port = port_name
        ser.baudrate = SERIAL_BAUDRATE
        ser.timeout = SERIAL_TIMEOUT
        ser.write_timeout = SERIAL_TIMEOUT
        if self.system_name != "windows" and hasattr(ser, "exclusive"):
            ser.exclusive = False
        ser.open()
        time.sleep(0.15)
        try:
            ser.reset_input_buffer()
        except Exception:
            pass
        try:
            ser.reset_output_buffer()
        except Exception:
            pass
        if SERIAL_HANDSHAKE_ENABLED and not self._probe_serial_port(ser):
            try:
                ser.close()
            except Exception:
                pass
            raise RuntimeError(f"serial handshake failed on {port_name}")
        return ser

    def _probe_serial_port(self, ser: serial.Serial) -> bool:
        deadline = time.time() + SERIAL_HANDSHAKE_TIMEOUT_SEC
        if SERIAL_HANDSHAKE_WRITE:
            try:
                ser.write(SERIAL_HANDSHAKE_WRITE)
                ser.flush()
            except Exception as exc:
                print(f"[WARN] handshake write failed on {ser.port}: {exc}")
                return False

        while not self.stop_event.is_set() and time.time() < deadline:
            try:
                raw = ser.readline()
            except Exception as exc:
                print(f"[WARN] handshake read failed on {ser.port}: {exc}")
                return False
            if not raw:
                continue
            try:
                line = raw.decode("utf-8", errors="ignore").strip()
            except Exception:
                continue
            if not line:
                continue
            if ARRAY_REGEX.search(line):
                self.line_queue.put((ser.port, line))
                print(f"[INFO] serial handshake ok: {ser.port}")
                return True
        return False

    def _close_serial_port(self, port_name: str | None = None) -> None:
        with self.serial_lock:
            ser = self.serial_handle
            if ser is None:
                return
            active_port = port_name or self.current_port or getattr(ser, "port", None)
            try:
                if ser.is_open:
                    try:
                        ser.cancel_read()
                    except Exception:
                        pass
                    try:
                        ser.reset_input_buffer()
                    except Exception:
                        pass
                    try:
                        ser.reset_output_buffer()
                    except Exception:
                        pass
                    ser.close()
                    print(f"[INFO] serial port released: {active_port}")
            except Exception as exc:
                print(f"[WARN] serial close failed: {active_port} ({exc})")
            finally:
                self.serial_handle = None
                if self.current_port == active_port:
                    self.current_port = None

    def _serial_reader(self, port_name: str) -> None:
        try:
            ser = self._open_serial_port(port_name)
            with self.serial_lock:
                self.serial_handle = ser
                self.current_port = port_name
            while not self.stop_event.is_set():
                raw = ser.readline()
                if not raw:
                    continue
                try:
                    line = raw.decode("utf-8", errors="ignore").strip()
                except Exception:
                    continue
                if line:
                    self.line_queue.put((port_name, line))
        except (OSError, Exception) as exc:
            print(f"[WARN] serial port closed: {port_name} ({exc})")
        finally:
            self._close_serial_port(port_name)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------
    def extract_array(self, line: str) -> list[float] | None:
        match = ARRAY_REGEX.search(line)
        raw = match.group(1) if match else line
        values = NUMBER_REGEX.findall(raw)
        if len(values) < MIN_VALID_ARRAY_LENGTH:
            return None
        try:
            return [float(item) for item in values]
        except ValueError:
            return None

    def build_payload_from_array(self, values: list[float]) -> dict[str, Any] | None:
        try:
            channels = [round(values[index], 3) for index in ARRAY_MAPPING["channels"]]
        except (IndexError, KeyError):
            return None

        def _pick(index_name: str, default: float | None = None) -> float | None:
            index = ARRAY_MAPPING.get(index_name)
            if index is None:
                return default
            if index >= len(values):
                return default
            return values[index]

        def _pick_bool(index_name: str, default: bool = False) -> bool:
            value = _pick(index_name, None)
            if value is None:
                return default
            return bool(int(value))

        alarm_indices = ARRAY_MAPPING.get("alarm_channels", [])
        alarm_channels = [int(values[index]) if index < len(values) else 0 for index in alarm_indices]

        telemetry: dict[str, Any] = {
            "seed_channels_g": channels,
            "seed_total_g": _pick("seed_total_g", sum(channels)),
            "distance_m": _pick("distance_m"),
            "leak_distance_m": _pick("leak_distance_m", 0.0),
            "speed_kmh": _pick("speed_kmh"),
            "alarm_channels": alarm_channels,
            "alarm_blocked": _pick_bool("alarm_blocked", any(value == 1 for value in alarm_channels)),
            "alarm_no_seed": _pick_bool("alarm_no_seed", False),
        }

        lon = _pick("lon")
        lat = _pick("lat")
        gps = None
        if lon is not None and lat is not None:
            gps = {"lon": lon, "lat": lat}

        if not telemetry and not gps:
            return None

        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "telemetry": telemetry,
            "gps": gps,
        }

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self) -> None:
        print("=" * 72)
        print("RSR serial_ingest_bridge.py")
        print("=" * 72)
        print(f"[INFO] system      : {self.system_name}")
        print(f"[INFO] cloud api   : {self.cloud.base_url}")

        last_scan_at = 0.0

        while not self.stop_event.is_set():
            now = time.time()
            if self.reader_thread is None or not self.reader_thread.is_alive():
                if now - last_scan_at >= SERIAL_SCAN_INTERVAL_SEC:
                    last_scan_at = now
                    candidates = self.list_candidate_ports()
                    if candidates:
                        best = candidates[0]
                        if self.current_port and self.current_port != best.device:
                            self._close_serial_port(self.current_port)
                        print(f"[INFO] selected serial candidate: {best.device} ({best.description})")
                        self.reader_thread = threading.Thread(
                            target=self._serial_reader,
                            args=(best.device,),
                            daemon=True,
                        )
                        self.reader_thread.start()
                    else:
                        print("[WARN] no serial port detected, rescanning...")

            try:
                port_name, line = self.line_queue.get(timeout=0.5)
            except queue.Empty:
                if self.current_run_id and self.last_valid_frame_at:
                    if time.time() - self.last_valid_frame_at >= RUN_IDLE_STOP_SEC:
                        self._finish_current_run("idle timeout")
                continue

            values = self.extract_array(line)
            if values is None:
                continue

            self.last_valid_frame_at = time.time()
            self.valid_frame_counter += 1
            payload = self.build_payload_from_array(values)
            if payload is None:
                continue

            if not self.current_run_id and self.valid_frame_counter >= SERIAL_STABLE_LINE_COUNT:
                try:
                    self.start_or_get_run()
                    self._replay_cached_payloads(force=True)
                except RequestException as exc:
                    print(f"[ERROR] failed to start/get run: {exc}")
                    time.sleep(1.0)
                    continue

            if not self.current_run_id:
                continue

            try:
                self.upload_ingest(payload)
                self._replay_cached_payloads()
                print(
                    "[DATA]",
                    json.dumps(
                        {
                            "port": port_name,
                            "seed_total_g": payload.get("telemetry", {}).get("seed_total_g"),
                            "distance_m": payload.get("telemetry", {}).get("distance_m"),
                            "gps": payload.get("gps"),
                        },
                        ensure_ascii=False,
                    ),
                )
            except RequestException as exc:
                print(f"[WARN] upload failed: {exc}")
                self._cache_failed_payload(payload, str(exc))
            except RuntimeError as exc:
                print(f"[WARN] server rejected ingest: {exc}")
                self._cache_failed_payload(payload, str(exc))
                self._reset_run_state()
                time.sleep(0.5)

            if self.current_run_id and self.last_valid_frame_at:
                if time.time() - self.last_valid_frame_at >= RUN_IDLE_STOP_SEC:
                    self._finish_current_run("idle timeout")

        self.shutdown()

    def shutdown(self) -> None:
        self.stop_event.set()
        if self.current_run_id:
            self._finish_current_run("bridge shutdown")
        self._close_serial_port()
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=2.0)
        self.reader_thread = None


def install_signal_handlers(bridge: SerialIngestBridge) -> None:
    def _handle_stop(signum: int, frame: Any) -> None:
        print(f"\n[INFO] stopping bridge, signal={signum}")
        bridge.stop_event.set()

    signal.signal(signal.SIGINT, _handle_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_stop)


def main() -> int:
    bridge = SerialIngestBridge(CloudConfig())
    install_signal_handlers(bridge)
    try:
        bridge.run()
        return 0
    except KeyboardInterrupt:
        bridge.shutdown()
        return 0
    except Exception as exc:
        print(f"[FATAL] {exc}")
        bridge.shutdown()
        return 1


if __name__ == "__main__":
    sys.exit(main())
