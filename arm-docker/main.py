#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import math
import os
import platform
import queue
import signal
import struct
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import requests
import serial
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from serial.tools import list_ports
from urllib3.util.retry import Retry

DEFAULTS = {
    "API_SCHEME": "http",
    "API_HOST": "127.0.0.1",
    "API_PORT": 8100,
    "API_PREFIX": "/api/v1",
    "ADMIN_TOKEN": "CHANGE_ME_ADMIN_TOKEN",
    "INGEST_TOKEN": "CHANGE_ME_INGEST_TOKEN",
    "REQUEST_CONNECT_TIMEOUT": 5.0,
    "REQUEST_READ_TIMEOUT": 15.0,
    "VERIFY_TLS": False,
    "DEBUG_LOG": False,
    "SERIAL_BAUDRATE": 115200,
    "SERIAL_TIMEOUT": 0.25,
    "SERIAL_READ_CHUNK_SIZE": 256,
    "SERIAL_REOPEN_DELAY_SEC": 2.0,
    "SERIAL_SCAN_INTERVAL_SEC": 3.0,
    "SERIAL_STABLE_FRAME_COUNT": 3,
    "RUN_IDLE_STOP_SEC": 30.0,
    "SERIAL_HANDSHAKE_ENABLED": True,
    "SERIAL_HANDSHAKE_TIMEOUT_SEC": 8.0,
    "SERIAL_HANDSHAKE_WRITE_HEX": "",
    "FAILED_CACHE_PATH": "./data/serial_cache.jsonl",
    "CACHE_REPLAY_BATCH_SIZE": 20,
    "CACHE_REPLAY_INTERVAL_SEC": 5.0,
    "LOG_FILE": "./logs/serial-bridge.log",
    "LOG_MAX_BYTES": 5 * 1024 * 1024,
    "LOG_BACKUP_COUNT": 5,
    "STATUS_HEARTBEAT_INTERVAL_SEC": 30.0,
    "HEARTBEAT_PATH": "./runtime/heartbeat.json",
}

FRAME_FLOAT_COUNT = 16
FRAME_SIZE = FRAME_FLOAT_COUNT * 4
MAX_BUFFER_BYTES = FRAME_SIZE * 8
ALARM_THRESHOLD = 0.5
DATA_SCALE = 10000.0
FLOAT_ROUND_DIGITS = 2
GPS_ROUND_DIGITS = 6

STATE_WAITING_PORT = "waiting_port"
STATE_PROBING = "probing"
STATE_WAITING_STABLE_FRAMES = "waiting_stable_frames"
STATE_RUNNING = "running"
STATE_IDLE_STOPPING = "idle_stopping"
STATE_STOPPED = "stopped"

logger = logging.getLogger("rsr.serial_agent")

SAMPLE_FRAME_VALUES = {
    "channels": [23.22, 24.53, 26.17, 23.91, 24.03],
    "speed_kmh": 0.0,
    "distance_m": 10.01,
    "lat_ddmm": 4249.78272,
    "lon_ddmm": 8917.85552,
    "leak_distance_m": 1.25,
    "uniformity_index": 0.0,
    "alarm_channels": [0, 0, 0, 0, 0],
}


class NoActiveRunError(RuntimeError):
    pass


class AuthFailureError(RuntimeError):
    pass


class ServerFailureError(RuntimeError):
    pass


@dataclass
class AppConfig:
    api_scheme: str
    api_host: str
    api_port: int
    api_prefix: str
    admin_token: str
    ingest_token: str
    request_connect_timeout: float
    request_read_timeout: float
    verify_tls: bool
    debug_log: bool
    serial_baudrate: int
    serial_timeout: float
    serial_read_chunk_size: int
    serial_reopen_delay_sec: float
    serial_scan_interval_sec: float
    serial_stable_frame_count: int
    run_idle_stop_sec: float
    serial_handshake_enabled: bool
    serial_handshake_timeout_sec: float
    serial_handshake_write_hex: str
    failed_cache_path: Path
    cache_replay_batch_size: int
    cache_replay_interval_sec: float
    log_file: Path
    log_max_bytes: int
    log_backup_count: int
    status_heartbeat_interval_sec: float
    heartbeat_path: Path

    @property
    def base_url(self) -> str:
        prefix = self.api_prefix if self.api_prefix.startswith("/") else f"/{self.api_prefix}"
        return f"{self.api_scheme}://{self.api_host}:{self.api_port}{prefix.rstrip('/')}"

    @property
    def request_timeout(self) -> tuple[float, float]:
        return (self.request_connect_timeout, self.request_read_timeout)

    @property
    def serial_handshake_write(self) -> bytes:
        text = self.serial_handshake_write_hex.replace(" ", "").strip()
        return bytes.fromhex(text) if text else b""


@dataclass
class SerialPortCandidate:
    device: str
    description: str
    score: int


@dataclass
class ParsedFrame:
    channel_values: list[float]
    speed_kmh: float
    distance_m: float
    lat: float
    lon: float
    leak_distance_m: float
    uniformity_index: float
    alarm_channels: list[int]
    raw_values: list[float]
    received_at: datetime


@dataclass
class FrameStats:
    parsed_frames: int = 0
    validation_failures: int = 0
    dropped_bytes: int = 0
    resync_count: int = 0


@dataclass
class RuntimeState:
    current_run_id: Optional[str] = None
    current_port: Optional[str] = None
    valid_frame_counter: int = 0
    last_valid_frame_at: float = 0.0
    last_success_port: Optional[str] = None
    state: str = STATE_WAITING_PORT
    upload_failures: int = 0
    total_uploaded_frames: int = 0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RSR ARM 串口采集上传 Agent")
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--port", default="")
    parser.add_argument("--config", default="")
    parser.add_argument("--log-file", default="")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--no-cache-replay", action="store_true")
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_config(args: argparse.Namespace) -> AppConfig:
    cfg_path = Path(args.config) if args.config else Path(__file__).with_name("settings.json")
    merged = dict(DEFAULTS)
    merged.update(_read_json(cfg_path))
    for key in DEFAULTS:
        if key in os.environ:
            merged[key] = os.environ[key]
    if args.log_file:
        merged["LOG_FILE"] = args.log_file
    if args.debug:
        merged["DEBUG_LOG"] = True
    return AppConfig(
        api_scheme=str(merged["API_SCHEME"]).strip().lower(),
        api_host=str(merged["API_HOST"]).strip(),
        api_port=int(merged["API_PORT"]),
        api_prefix=str(merged["API_PREFIX"]).strip(),
        admin_token=str(merged["ADMIN_TOKEN"]).strip(),
        ingest_token=str(merged["INGEST_TOKEN"]).strip(),
        request_connect_timeout=float(merged["REQUEST_CONNECT_TIMEOUT"]),
        request_read_timeout=float(merged["REQUEST_READ_TIMEOUT"]),
        verify_tls=_bool(merged["VERIFY_TLS"]),
        debug_log=_bool(merged["DEBUG_LOG"]),
        serial_baudrate=int(merged["SERIAL_BAUDRATE"]),
        serial_timeout=float(merged["SERIAL_TIMEOUT"]),
        serial_read_chunk_size=int(merged["SERIAL_READ_CHUNK_SIZE"]),
        serial_reopen_delay_sec=float(merged["SERIAL_REOPEN_DELAY_SEC"]),
        serial_scan_interval_sec=float(merged["SERIAL_SCAN_INTERVAL_SEC"]),
        serial_stable_frame_count=int(merged["SERIAL_STABLE_FRAME_COUNT"]),
        run_idle_stop_sec=float(merged["RUN_IDLE_STOP_SEC"]),
        serial_handshake_enabled=_bool(merged["SERIAL_HANDSHAKE_ENABLED"]),
        serial_handshake_timeout_sec=float(merged["SERIAL_HANDSHAKE_TIMEOUT_SEC"]),
        serial_handshake_write_hex=str(merged["SERIAL_HANDSHAKE_WRITE_HEX"]),
        failed_cache_path=Path(str(merged["FAILED_CACHE_PATH"])),
        cache_replay_batch_size=int(merged["CACHE_REPLAY_BATCH_SIZE"]),
        cache_replay_interval_sec=float(merged["CACHE_REPLAY_INTERVAL_SEC"]),
        log_file=Path(str(merged["LOG_FILE"])),
        log_max_bytes=int(merged["LOG_MAX_BYTES"]),
        log_backup_count=int(merged["LOG_BACKUP_COUNT"]),
        status_heartbeat_interval_sec=float(merged["STATUS_HEARTBEAT_INTERVAL_SEC"]),
        heartbeat_path=Path(str(merged["HEARTBEAT_PATH"])),
    )


def setup_logging(config: AppConfig) -> None:
    level = logging.DEBUG if config.debug_log else logging.INFO
    logger.setLevel(level)
    logger.handlers.clear()
    logger.propagate = False
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(fmt)
    logger.addHandler(console)
    config.log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        config.log_file, maxBytes=config.log_max_bytes, backupCount=config.log_backup_count, encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)


def log_config_summary(config: AppConfig) -> None:
    logger.info(
        "配置摘要: api=%s serial_baudrate=%s serial_timeout=%.2f stable_frames=%s idle_stop=%.1fs cache=%s log=%s heartbeat=%s debug=%s",
        config.base_url,
        config.serial_baudrate,
        config.serial_timeout,
        config.serial_stable_frame_count,
        config.run_idle_stop_sec,
        config.failed_cache_path,
        config.log_file,
        config.heartbeat_path,
        config.debug_log,
    )


def round2(value: float) -> float:
    return round(float(value), FLOAT_ROUND_DIGITS)


def round_gps(value: float) -> float:
    return round(float(value), GPS_ROUND_DIGITS)


def parse_float_le(chunk4: bytes) -> float:
    if len(chunk4) != 4:
        raise ValueError("float chunk must be 4 bytes")
    return struct.unpack("<f", chunk4)[0]


def decode_scaled_value(raw_value: float) -> float:
    return round2(raw_value / DATA_SCALE)


def ddmm_to_decimal_degrees(ddmm_value: float) -> float:
    abs_value = abs(ddmm_value)
    degrees = int(abs_value // 100)
    minutes = abs_value - degrees * 100
    decimal = degrees + minutes / 60.0
    if ddmm_value < 0:
        decimal *= -1
    return round_gps(decimal)


def decode_gps_value(raw_value: float) -> float:
    restored_ddmm = raw_value / DATA_SCALE
    return ddmm_to_decimal_degrees(restored_ddmm)


def parse_frame(frame_bytes: bytes) -> ParsedFrame:
    if len(frame_bytes) != FRAME_SIZE:
        raise ValueError(f"frame size must be {FRAME_SIZE} bytes")
    values = [parse_float_le(frame_bytes[i:i + 4]) for i in range(0, FRAME_SIZE, 4)]
    alarms = [1 if values[i] >= ALARM_THRESHOLD else 0 for i in range(11, 16)]
    return ParsedFrame(
        channel_values=[decode_scaled_value(values[i]) for i in range(5)],
        speed_kmh=decode_scaled_value(values[5]),
        distance_m=decode_scaled_value(values[6]),
        lat=decode_gps_value(values[7]),
        lon=decode_gps_value(values[8]),
        leak_distance_m=decode_scaled_value(values[9]),
        uniformity_index=decode_scaled_value(values[10]),
        alarm_channels=alarms,
        raw_values=values,
        received_at=datetime.now(timezone.utc),
    )


def validate_frame(frame: ParsedFrame) -> bool:
    return (
        len(frame.raw_values) == FRAME_FLOAT_COUNT
        and all(math.isfinite(v) for v in frame.raw_values)
        and all(v >= 0 for v in frame.channel_values)
        and frame.speed_kmh >= 0
        and frame.distance_m >= 0
        and frame.leak_distance_m >= 0
        and -90 <= frame.lat <= 90
        and -180 <= frame.lon <= 180
        and all(a in (0, 1) for a in frame.alarm_channels)
    )


class SerialFrameAssembler:
    def __init__(self, stats: FrameStats) -> None:
        self.buffer = bytearray()
        self.locked = False
        self.stats = stats

    def append(self, data: bytes) -> None:
        if data:
            self.buffer.extend(data)

    def pop_frames(self) -> list[ParsedFrame]:
        frames: list[ParsedFrame] = []
        while True:
            frame = self._extract_one()
            if frame is None:
                break
            frames.append(frame)
        self._trim_buffer_if_needed()
        return frames

    def _extract_one(self) -> Optional[ParsedFrame]:
        if len(self.buffer) < FRAME_SIZE:
            return None
        if self.locked:
            frame = self._try_offset(0)
            if frame is not None:
                del self.buffer[:FRAME_SIZE]
                self.stats.parsed_frames += 1
                return frame
            self.locked = False
            logger.warning("帧锁定丢失，进入重同步，缓冲区=%s", len(self.buffer))
        return self._search(4) or self._search(1)

    def _search(self, step: int) -> Optional[ParsedFrame]:
        max_offset = len(self.buffer) - FRAME_SIZE
        for offset in range(0, max_offset + 1, step):
            frame = self._try_offset(offset)
            if frame is None:
                continue
            if offset:
                self.stats.dropped_bytes += offset
                self.stats.resync_count += 1
                logger.info("重同步成功，丢弃=%s字节", offset)
            del self.buffer[:offset + FRAME_SIZE]
            self.locked = True
            self.stats.parsed_frames += 1
            return frame
        return None

    def _try_offset(self, offset: int) -> Optional[ParsedFrame]:
        if offset + FRAME_SIZE > len(self.buffer):
            return None
        try:
            parsed = parse_frame(bytes(self.buffer[offset:offset + FRAME_SIZE]))
        except Exception:
            self.stats.validation_failures += 1
            return None
        if not validate_frame(parsed):
            self.stats.validation_failures += 1
            return None
        return parsed

    def _trim_buffer_if_needed(self) -> None:
        if len(self.buffer) <= MAX_BUFFER_BYTES:
            return
        drop = len(self.buffer) - (FRAME_SIZE - 1)
        del self.buffer[:drop]
        self.stats.dropped_bytes += drop
        self.locked = False
        logger.warning("缓冲区过长，丢弃=%s字节", drop)


class SerialIngestAgent:
    def __init__(self, config: AppConfig, preferred_port: str = "", run_once: bool = False, replay_cache: bool = True) -> None:
        self.config = config
        self.preferred_port = preferred_port.strip()
        self.run_once = run_once
        self.replay_cache = replay_cache
        self.system_name = platform.system().lower()
        self.stop_event = threading.Event()
        self.frame_queue: queue.Queue[tuple[str, ParsedFrame]] = queue.Queue()
        self.serial_lock = threading.Lock()
        self.serial_handle: Optional[serial.Serial] = None
        self.reader_thread: Optional[threading.Thread] = None
        self.cache_lock = threading.Lock()
        self.state = RuntimeState()
        self.frame_stats = FrameStats()
        self.last_heartbeat_at = 0.0
        self.session = self._build_session()

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        session.verify = self.config.verify_tls
        session.headers.update({"User-Agent": "rsr-arm-agent/1.0"})
        retry = Retry(total=3, connect=3, read=2, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504], allowed_methods=frozenset({"GET", "POST"}), raise_on_status=False)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _set_state(self, value: str) -> None:
        if self.state.state != value:
            logger.info("状态切换: %s -> %s", self.state.state, value)
            self.state.state = value

    def _admin_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.config.admin_token}", "Content-Type": "application/json"}

    def _ingest_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.config.ingest_token}", "Content-Type": "application/json"}

    def _count_cache(self) -> int:
        if not self.config.failed_cache_path.exists():
            return 0
        with self.config.failed_cache_path.open("r", encoding="utf-8") as fh:
            return sum(1 for line in fh if line.strip())

    def _write_heartbeat(self) -> None:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "state": self.state.state,
            "current_port": self.state.current_port,
            "current_run_id": self.state.current_run_id,
            "last_valid_frame_at": self.state.last_valid_frame_at,
            "parsed_frames": self.frame_stats.parsed_frames,
            "validation_failures": self.frame_stats.validation_failures,
            "cache_backlog": self._count_cache(),
            "upload_failures": self.state.upload_failures,
        }
        self.config.heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.config.heartbeat_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.config.heartbeat_path)

    def _emit_heartbeat(self) -> None:
        now = time.time()
        if now - self.last_heartbeat_at < self.config.status_heartbeat_interval_sec:
            return
        self.last_heartbeat_at = now
        self._write_heartbeat()
        logger.info(
            "状态心跳: state=%s port=%s run=%s parsed=%s invalid=%s cache=%s upload_failures=%s",
            self.state.state, self.state.current_port, self.state.current_run_id,
            self.frame_stats.parsed_frames, self.frame_stats.validation_failures,
            self._count_cache(), self.state.upload_failures,
        )

    def list_candidate_ports(self) -> list[SerialPortCandidate]:
        if self.preferred_port:
            return [SerialPortCandidate(self.preferred_port, "manual", 999)]
        items: list[SerialPortCandidate] = []
        keywords = ("usb", "serial", "uart", "ch340", "ch330", "cp210", "ftdi", "ttyusb", "ttyacm", "com")
        for port in list_ports.comports():
            text = " ".join(str(v).lower() for v in [port.device, port.description, port.manufacturer, port.product] if v)
            score = sum(10 for k in keywords if k in text)
            if self.state.last_success_port and port.device == self.state.last_success_port:
                score += 50
            if "bluetooth" in text:
                score -= 20
            items.append(SerialPortCandidate(port.device, port.description or "", max(score, 1)))
        items.sort(key=lambda x: x.score, reverse=True)
        return items

    def _open_serial(self, port_name: str) -> serial.Serial:
        logger.info("打开串口: %s @ %s", port_name, self.config.serial_baudrate)
        ser = serial.Serial()
        ser.port = port_name
        ser.baudrate = self.config.serial_baudrate
        ser.timeout = self.config.serial_timeout
        ser.write_timeout = self.config.serial_timeout
        if self.system_name != "windows" and hasattr(ser, "exclusive"):
            ser.exclusive = False
        ser.open()
        time.sleep(0.15)
        try:
            ser.reset_input_buffer()
            ser.reset_output_buffer()
        except Exception:
            pass
        return ser

    def _probe(self, ser: serial.Serial) -> bool:
        self._set_state(STATE_PROBING)
        assembler = SerialFrameAssembler(FrameStats())
        deadline = time.time() + self.config.serial_handshake_timeout_sec
        write_bytes = self.config.serial_handshake_write
        if write_bytes:
            try:
                ser.write(write_bytes)
                ser.flush()
            except Exception as exc:
                logger.warning("握手写入失败: %s", exc)
                return False
        while not self.stop_event.is_set() and time.time() < deadline:
            raw = ser.read(FRAME_SIZE)
            if not raw:
                continue
            assembler.append(raw)
            frames = assembler.pop_frames()
            if frames:
                port_name = str(ser.port)
                self.frame_queue.put((port_name, frames[0]))
                logger.info("握手成功: %s", port_name)
                return True
        logger.warning("握手超时: %s", ser.port)
        return False

    def _close_serial(self, port_name: Optional[str] = None) -> None:
        with self.serial_lock:
            ser = self.serial_handle
            if ser is None:
                return
            active = port_name or self.state.current_port or getattr(ser, "port", None)
            try:
                if ser.is_open:
                    try:
                        ser.cancel_read()
                    except Exception:
                        pass
                    try:
                        ser.reset_input_buffer()
                        ser.reset_output_buffer()
                    except Exception:
                        pass
                    ser.close()
                    logger.info("串口已释放: %s", active)
            except Exception as exc:
                logger.warning("串口关闭失败: %s", exc)
            finally:
                self.serial_handle = None
                if self.state.current_port == active:
                    self.state.current_port = None

    def _reader(self, port_name: str) -> None:
        assembler = SerialFrameAssembler(self.frame_stats)
        try:
            ser = self._open_serial(port_name)
            if self.config.serial_handshake_enabled and not self._probe(ser):
                ser.close()
                raise RuntimeError(f"handshake failed on {port_name}")
            with self.serial_lock:
                self.serial_handle = ser
                self.state.current_port = port_name
                self.state.last_success_port = port_name
            logger.info("串口读线程启动: %s", port_name)
            while not self.stop_event.is_set():
                raw = ser.read(self.config.serial_read_chunk_size)
                if not raw:
                    continue
                assembler.append(raw)
                for frame in assembler.pop_frames():
                    self.frame_queue.put((port_name, frame))
                if self.config.debug_log and assembler.buffer:
                    logger.debug("串口缓存长度=%s", len(assembler.buffer))
        except Exception as exc:
            logger.warning("串口线程退出: port=%s error=%s", port_name, exc)
            time.sleep(self.config.serial_reopen_delay_sec)
        finally:
            self._close_serial(port_name)

    def _build_payload(self, frame: ParsedFrame) -> dict[str, Any]:
        return {
            "ts": frame.received_at.isoformat(),
            "telemetry": {
                "seed_channels_g": frame.channel_values,
                "seed_total_g": round2(sum(frame.channel_values)),
                "distance_m": frame.distance_m,
                "leak_distance_m": frame.leak_distance_m,
                "speed_kmh": frame.speed_kmh,
                "uniformity_index": frame.uniformity_index,
                "alarm_channels": frame.alarm_channels,
                "alarm_blocked": any(v == 1 for v in frame.alarm_channels),
                "alarm_no_seed": False,
            },
            "gps": {"lon": frame.lon, "lat": frame.lat},
        }

    def _append_cache_line(self, line: str) -> None:
        self.config.failed_cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config.failed_cache_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def _cache_payload(self, payload: dict[str, Any], reason: str) -> None:
        record = {"cached_at": datetime.now(timezone.utc).isoformat(), "reason": reason, "payload": payload}
        with self.cache_lock:
            self._append_cache_line(json.dumps(record, ensure_ascii=False))
        logger.warning("payload 已缓存: reason=%s", reason)

    def _rewrite_cache(self, remaining: list[str]) -> None:
        tmp = self.config.failed_cache_path.with_suffix(self.config.failed_cache_path.suffix + ".tmp")
        if remaining:
            with tmp.open("w", encoding="utf-8") as fh:
                fh.write("\n".join(remaining) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.config.failed_cache_path)
        else:
            if tmp.exists():
                tmp.unlink()
            if self.config.failed_cache_path.exists():
                self.config.failed_cache_path.unlink()

    def _upload(self, payload: dict[str, Any]) -> None:
        resp = self.session.post(f"{self.config.base_url}/ingest", headers=self._ingest_headers(), json=payload, timeout=self.config.request_timeout)
        if resp.status_code == 202:
            return
        if resp.status_code in (401, 403):
            raise AuthFailureError(str(resp.status_code))
        if resp.status_code == 409:
            self.state.current_run_id = None
            raise NoActiveRunError("409")
        if resp.status_code >= 500:
            raise ServerFailureError(str(resp.status_code))
        resp.raise_for_status()

    def _start_run(self) -> None:
        resp = self.session.post(f"{self.config.base_url}/runs/start", headers=self._admin_headers(), json={}, timeout=self.config.request_timeout)
        resp.raise_for_status()
        data = resp.json()
        self.state.current_run_id = data["run_id"]
        logger.info("任务已激活: run_id=%s", self.state.current_run_id)

    def _stop_run(self) -> None:
        if not self.state.current_run_id:
            return
        run_id = self.state.current_run_id
        try:
            resp = self.session.post(f"{self.config.base_url}/runs/{run_id}/stop", headers=self._admin_headers(), timeout=self.config.request_timeout)
            resp.raise_for_status()
            logger.info("任务已停止: run_id=%s", run_id)
        except Exception as exc:
            logger.warning("停止任务失败: run_id=%s error=%s", run_id, exc)
        finally:
            self.state.current_run_id = None

    def _replay_cache(self, force: bool = False) -> None:
        if not self.replay_cache or not self.config.failed_cache_path.exists():
            return
        lines = self.config.failed_cache_path.read_text(encoding="utf-8").splitlines()
        remaining: list[str] = []
        replayed = 0
        damaged = 0
        for line in lines:
            if not line.strip():
                continue
            if not force and replayed >= self.config.cache_replay_batch_size:
                remaining.append(line)
                continue
            try:
                payload = json.loads(line).get("payload")
                if not payload:
                    damaged += 1
                    continue
                self._upload(payload)
                replayed += 1
            except json.JSONDecodeError:
                damaged += 1
            except Exception:
                remaining.append(line)
        with self.cache_lock:
            self._rewrite_cache(remaining)
        if replayed or damaged:
            logger.info("缓存回放: replayed=%s damaged=%s remaining=%s", replayed, damaged, len(remaining))

    def _finish_run(self, reason: str) -> None:
        if not self.state.current_run_id:
            return
        self._set_state(STATE_IDLE_STOPPING)
        logger.info("结束当前任务: run_id=%s reason=%s", self.state.current_run_id, reason)
        self._replay_cache(force=True)
        self._stop_run()
        self.state.valid_frame_counter = 0
        self.state.last_valid_frame_at = 0.0
        self._set_state(STATE_WAITING_STABLE_FRAMES)

    def _start_reader_if_needed(self) -> None:
        if self.reader_thread and self.reader_thread.is_alive():
            return
        ports = self.list_candidate_ports()
        if not ports:
            self._set_state(STATE_WAITING_PORT)
            logger.warning("未发现可用串口")
            return
        best = ports[0]
        self._set_state(STATE_PROBING if self.config.serial_handshake_enabled else STATE_WAITING_STABLE_FRAMES)
        logger.info("选择串口候选: %s (%s)", best.device, best.description)
        self.reader_thread = threading.Thread(target=self._reader, args=(best.device,), daemon=True, name="serial-reader")
        self.reader_thread.start()

    def run(self) -> None:
        logger.info("Agent 启动: system=%s api=%s", platform.system(), self.config.base_url)
        self._set_state(STATE_WAITING_PORT)
        last_scan_at = 0.0
        while not self.stop_event.is_set():
            now = time.time()
            if now - last_scan_at >= self.config.serial_scan_interval_sec:
                last_scan_at = now
                self._start_reader_if_needed()
            self._emit_heartbeat()
            try:
                port_name, frame = self.frame_queue.get(timeout=0.5)
            except queue.Empty:
                if self.state.current_run_id and self.state.last_valid_frame_at and time.time() - self.state.last_valid_frame_at >= self.config.run_idle_stop_sec:
                    self._finish_run("idle timeout")
                continue
            self.state.last_valid_frame_at = time.time()
            self.state.valid_frame_counter += 1
            if not self.state.current_run_id:
                self._set_state(STATE_WAITING_STABLE_FRAMES)
            payload = self._build_payload(frame)
            if self.config.debug_log:
                logger.debug("收到有效帧: port=%s channels=%s gps=(%.5f,%.5f)", port_name, frame.channel_values, frame.lat, frame.lon)
            if not self.state.current_run_id and self.state.valid_frame_counter >= self.config.serial_stable_frame_count:
                try:
                    self._start_run()
                    self._set_state(STATE_RUNNING)
                    self._replay_cache(force=True)
                except RequestException as exc:
                    logger.error("启动任务失败: %s", exc)
                    time.sleep(1.0)
                    continue
            if not self.state.current_run_id:
                continue
            try:
                self._upload(payload)
                self.state.total_uploaded_frames += 1
                if self.replay_cache:
                    self._replay_cache(force=False)
                logger.info("上传成功: port=%s total_seed=%.2f speed=%.2f distance=%.2f gps=(%.5f,%.5f)", port_name, sum(frame.channel_values), frame.speed_kmh, frame.distance_m, frame.lat, frame.lon)
                if self.run_once:
                    logger.info("--once 已满足，准备退出")
                    self.stop_event.set()
            except NoActiveRunError:
                self.state.upload_failures += 1
                self._cache_payload(payload, "no active run")
                try:
                    self._start_run()
                    self._set_state(STATE_RUNNING)
                except RequestException as exc:
                    logger.error("重建任务失败: %s", exc)
            except AuthFailureError as exc:
                self.state.upload_failures += 1
                logger.error("认证失败: %s", exc)
                self._cache_payload(payload, f"auth failed: {exc}")
                time.sleep(2.0)
            except (ServerFailureError, RequestException) as exc:
                self.state.upload_failures += 1
                logger.warning("上传失败: %s", exc)
                self._cache_payload(payload, str(exc))

        self.shutdown()

    def shutdown(self) -> None:
        logger.info("开始优雅退出")
        self.stop_event.set()
        self._replay_cache(force=True)
        if self.state.current_run_id:
            self._finish_run("agent shutdown")
        self._close_serial()
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=2.0)
        self.reader_thread = None
        self._set_state(STATE_STOPPED)
        self._emit_heartbeat()
        logger.info("Agent 已停止")


def sample_frame_bytes() -> bytes:
    encoded_values = [
        *(value * DATA_SCALE for value in SAMPLE_FRAME_VALUES["channels"]),
        SAMPLE_FRAME_VALUES["speed_kmh"] * DATA_SCALE,
        SAMPLE_FRAME_VALUES["distance_m"] * DATA_SCALE,
        SAMPLE_FRAME_VALUES["lat_ddmm"] * DATA_SCALE,
        SAMPLE_FRAME_VALUES["lon_ddmm"] * DATA_SCALE,
        SAMPLE_FRAME_VALUES["leak_distance_m"] * DATA_SCALE,
        SAMPLE_FRAME_VALUES["uniformity_index"] * DATA_SCALE,
        *(float(value) for value in SAMPLE_FRAME_VALUES["alarm_channels"]),
    ]
    return b"".join(struct.pack("<f", value) for value in encoded_values)


def run_self_check() -> None:
    print("[CHECK] 开始自检")
    sample = sample_frame_bytes()
    frame = parse_frame(sample)
    assert validate_frame(frame)
    expected_channels = [23.22, 24.53, 26.17, 23.91, 24.03]
    for actual, expected in zip(frame.channel_values, expected_channels):
        assert abs(actual - expected) <= 0.02, (actual, expected)
    assert abs(frame.distance_m - 10.01) <= 0.02, frame.distance_m
    assert abs(frame.lat - 42.829712) <= 0.00001, frame.lat
    assert abs(frame.lon - 89.297592) <= 0.00001, frame.lon
    stats = FrameStats()
    assembler = SerialFrameAssembler(stats)
    assembler.append(sample[:20])
    assert len(assembler.pop_frames()) == 0
    assembler.append(sample[20:])
    assert len(assembler.pop_frames()) == 1
    assembler = SerialFrameAssembler(FrameStats())
    assembler.append(sample + sample)
    assert len(assembler.pop_frames()) == 2
    assembler = SerialFrameAssembler(FrameStats())
    assembler.append(b"\x00\x01\x02" + sample)
    assert len(assembler.pop_frames()) == 1
    cfg = build_config(argparse.Namespace(self_check=False, port="", config="", log_file="", once=False, no_cache_replay=False, debug=False))
    agent = SerialIngestAgent(cfg, replay_cache=False)
    payload = agent._build_payload(frame)
    assert abs(payload["telemetry"]["seed_total_g"] - 121.86) <= 0.05
    assert payload["telemetry"]["alarm_no_seed"] is False
    assert abs(payload["gps"]["lat"] - 42.829712) <= 0.00001
    assert abs(payload["gps"]["lon"] - 89.297592) <= 0.00001
    print("[CHECK] 全部通过")


def install_signal_handlers(agent: SerialIngestAgent) -> None:
    def _handle(signum: int, frame: Any) -> None:
        logger.info("收到退出信号: signal=%s", signum)
        agent.stop_event.set()
    signal.signal(signal.SIGINT, _handle)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle)


def main() -> int:
    args = parse_args()
    if args.self_check:
        run_self_check()
        return 0
    config = build_config(args)
    setup_logging(config)
    log_config_summary(config)
    agent = SerialIngestAgent(config, preferred_port=args.port, run_once=args.once, replay_cache=not args.no_cache_replay)
    install_signal_handlers(agent)
    try:
        agent.run()
        return 0
    except KeyboardInterrupt:
        agent.shutdown()
        return 0
    except Exception:
        logger.exception("Agent 异常退出")
        agent.shutdown()
        return 1


if __name__ == "__main__":
    sys.exit(main())
