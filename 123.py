#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RSR 串口桥接脚本

能力：
1. 自动识别 Windows / Linux 环境。
2. 自动扫描最可能的 USB 串口设备。
3. 持续监听 STM32 发来的 64 字节二进制帧。
4. 自动创建 / 停止 run，并上传到后端 /api/v1/ingest。
5. 上传失败时把完整 payload 写入本地缓存，并在后续自动回放。
6. 长时间没有有效帧时自动结束当前任务，随后继续等待下一轮数据。
7. 内置最小自检，可验证字节序、半包、粘包与脏数据重同步。
"""

from __future__ import annotations

import argparse
import json
import math
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
from typing import Any

import requests
import serial
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
# 是否输出详细调试日志；常驻运行建议保持 False。
DEBUG_LOG = False
# 串口波特率，需与单片机固件一致。
SERIAL_BAUDRATE = 115200
# 串口读超时，单位秒。
SERIAL_TIMEOUT = 0.25
# 每次尽量从串口批量读取的字节数。
SERIAL_READ_CHUNK_SIZE = 256
# 串口异常断开后，重新尝试前的等待时间。
SERIAL_REOPEN_DELAY_SEC = 2.0
# 扫描可用串口的间隔时间。
SERIAL_SCAN_INTERVAL_SEC = 3.0
# 连续收到多少帧有效数据后，才自动开始任务。
SERIAL_STABLE_FRAME_COUNT = 3
# 当前任务在多久没有收到有效数据后，自动判定为结束，单位秒。
RUN_IDLE_STOP_SEC = 30.0
# 是否启用串口握手探测。
SERIAL_HANDSHAKE_ENABLED = True
# 打开串口后，最多等待多久来判断这个串口是不是目标设备。
SERIAL_HANDSHAKE_TIMEOUT_SEC = 8.0
# 如果设备需要先发唤醒命令，在这里填写字节串；默认空表示被动等待设备发数。
SERIAL_HANDSHAKE_WRITE = b""


# ============================================================================
# Cache config
# ============================================================================
# 上传失败时，本地缓存文件路径。
FAILED_CACHE_PATH = "serial_cache.jsonl"
# 每次最多回放多少条缓存数据，避免一次性阻塞主循环。
CACHE_REPLAY_BATCH_SIZE = 20
# 两次缓存回放之间的最小间隔，单位秒。
CACHE_REPLAY_INTERVAL_SEC = 5.0


# ============================================================================
# Frame protocol config
# ============================================================================
FRAME_FLOAT_COUNT = 16
FRAME_SIZE = FRAME_FLOAT_COUNT * 4
MAX_BUFFER_BYTES = FRAME_SIZE * 8
FLOAT_ROUND_DIGITS = 2
ALARM_THRESHOLD = 0.5
GPS_SCALE = 100000.0
GPS_ROUND_DIGITS = 5

# 样例 16 个 float 的原始 64 字节数据，用于自检。
SAMPLE_FRAME_HEX_LINES = [
    "4D BF B9 41",
    "86 47 C4 41",
    "B2 58 D1 41",
    "89 45 BF 41",
    "57 36 C0 41",
    "00 00 00 00",
    "C9 20 20 41",
    "A0 51 2B 42",
    "5E 98 B2 42",
    "DE BF 9F 3F",
    "00 00 00 00",
    "00 00 00 00",
    "00 00 00 00",
    "00 00 00 00",
    "00 00 00 00",
    "00 00 00 00",
]


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RSR STM32 串口桥接脚本")
    parser.add_argument("--self-check", action="store_true", help="只运行协议自检，不连接串口")
    parser.add_argument("--port", default="", help="手动指定串口号，例如 COM3 或 /dev/ttyUSB0")
    return parser.parse_args()


def round2(value: float) -> float:
    return round(float(value), FLOAT_ROUND_DIGITS)


def round_gps(value: float) -> float:
    return round(float(value), GPS_ROUND_DIGITS)


def debug_log(message: str) -> None:
    if DEBUG_LOG:
        print(f"[DEBUG] {message}")


def parse_float_le(chunk4: bytes) -> float:
    if len(chunk4) != 4:
        raise ValueError("float chunk must be 4 bytes")
    return struct.unpack("<f", chunk4)[0]


def decode_gps_value(raw_value: float) -> float:
    # 新协议：单片机先把经纬度放大 100000，再编码成 float 发送。
    # 为了兼容当前仓库里的旧自检样例，这里保留一个温和兼容：
    # 只有明显大于常规经纬度范围时才执行缩放还原。
    if abs(raw_value) > 180:
        return round_gps(raw_value / GPS_SCALE)
    return round_gps(raw_value)


def parse_frame(frame_bytes: bytes) -> ParsedFrame:
    if len(frame_bytes) != FRAME_SIZE:
        raise ValueError(f"frame size must be {FRAME_SIZE} bytes")

    values = [parse_float_le(frame_bytes[index:index + 4]) for index in range(0, FRAME_SIZE, 4)]
    alarms = [1 if values[index] >= ALARM_THRESHOLD else 0 for index in range(11, 16)]
    return ParsedFrame(
        channel_values=[round2(values[i]) for i in range(5)],
        speed_kmh=round2(values[5]),
        distance_m=round2(values[6]),
        lat=decode_gps_value(values[7]),
        lon=decode_gps_value(values[8]),
        leak_distance_m=round2(values[9]),
        uniformity_index=round2(values[10]),
        alarm_channels=alarms,
        raw_values=values,
        received_at=datetime.now(timezone.utc),
    )


def validate_frame(frame: ParsedFrame) -> bool:
    if len(frame.raw_values) != FRAME_FLOAT_COUNT:
        return False
    if any(not math.isfinite(value) for value in frame.raw_values):
        return False
    if any(value < 0 for value in frame.channel_values):
        return False
    if frame.speed_kmh < 0 or frame.distance_m < 0 or frame.leak_distance_m < 0:
        return False
    if not (-90 <= frame.lat <= 90):
        return False
    if not (-180 <= frame.lon <= 180):
        return False
    if any(alarm not in (0, 1) for alarm in frame.alarm_channels):
        return False
    return True


class SerialFrameAssembler:
    def __init__(self) -> None:
        self.buffer = bytearray()
        self.locked = False

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

    def _extract_one(self) -> ParsedFrame | None:
        if len(self.buffer) < FRAME_SIZE:
            return None

        if self.locked:
            frame = self._try_frame_at_offset(0)
            if frame is not None:
                del self.buffer[:FRAME_SIZE]
                return frame
            self.locked = False
            print(f"[WARN] 帧锁定丢失，进入重同步，当前缓冲区 {len(self.buffer)} 字节")

        aligned = self._search_with_step(4)
        if aligned is not None:
            return aligned

        bytewise = self._search_with_step(1)
        if bytewise is not None:
            return bytewise

        return None

    def _search_with_step(self, step: int) -> ParsedFrame | None:
        max_offset = len(self.buffer) - FRAME_SIZE
        for offset in range(0, max_offset + 1, step):
            frame = self._try_frame_at_offset(offset)
            if frame is None:
                continue
            if offset > 0:
                print(f"[INFO] 重同步成功，丢弃 {offset} 字节脏数据，缓冲区剩余 {len(self.buffer) - offset} 字节")
            del self.buffer[:offset + FRAME_SIZE]
            self.locked = True
            return frame
        return None

    def _try_frame_at_offset(self, offset: int) -> ParsedFrame | None:
        if offset + FRAME_SIZE > len(self.buffer):
            return None
        candidate = bytes(self.buffer[offset:offset + FRAME_SIZE])
        try:
            parsed = parse_frame(candidate)
        except Exception:
            return None
        return parsed if validate_frame(parsed) else None

    def _trim_buffer_if_needed(self) -> None:
        if len(self.buffer) <= MAX_BUFFER_BYTES:
            return
        drop = len(self.buffer) - (FRAME_SIZE - 1)
        del self.buffer[:drop]
        self.locked = False
        print(f"[WARN] 缓冲区过长，丢弃 {drop} 字节，保留 {len(self.buffer)} 字节等待重同步")


class SerialIngestBridge:
    def __init__(self, cloud: CloudConfig, preferred_port: str = "") -> None:
        self.cloud = cloud
        self.preferred_port = preferred_port.strip()
        self.session = requests.Session()
        self.session.verify = cloud.verify_tls
        self.session.headers.update({"User-Agent": "rsr-serial-bridge/2.0"})

        self.stop_event = threading.Event()
        self.frame_queue: queue.Queue[tuple[str, ParsedFrame]] = queue.Queue()

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
    # Serial discovery / IO
    # ------------------------------------------------------------------
    def list_candidate_ports(self) -> list[SerialPortCandidate]:
        if self.preferred_port:
            return [SerialPortCandidate(device=self.preferred_port, description="manual", score=999)]

        candidates: list[SerialPortCandidate] = []
        keywords = ("usb", "serial", "uart", "ch340", "ch330", "cp210", "ftdi", "ttyusb", "ttyacm", "com")
        for port in list_ports.comports():
            text = " ".join(
                str(value).lower()
                for value in [port.device, port.description, port.manufacturer, port.product]
                if value
            )
            score = sum(10 for keyword in keywords if keyword in text)
            if "bluetooth" in text:
                score -= 20
            candidates.append(
                SerialPortCandidate(
                    device=port.device,
                    description=port.description or "",
                    score=max(score, 1),
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
        assembler = SerialFrameAssembler()
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
                raw = ser.read(FRAME_SIZE)
            except Exception as exc:
                print(f"[WARN] handshake read failed on {ser.port}: {exc}")
                return False
            if not raw:
                continue
            assembler.append(raw)
            frames = assembler.pop_frames()
            if frames:
                port_name = str(ser.port)
                self.frame_queue.put((port_name, frames[0]))
                print(f"[INFO] serial handshake ok: {port_name}")
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
        assembler = SerialFrameAssembler()
        try:
            ser = self._open_serial_port(port_name)
            with self.serial_lock:
                self.serial_handle = ser
                self.current_port = port_name

            debug_log(f"serial reader started on {port_name}")
            
            while not self.stop_event.is_set():
                raw = ser.read(SERIAL_READ_CHUNK_SIZE)
                if not raw:
                    continue
                assembler.append(raw)
                frames = assembler.pop_frames()
                if frames:
                    for frame in frames:
                        self.frame_queue.put((port_name, frame))
                    debug_log(f"extracted {len(frames)} frame(s), buffer size: {len(assembler.buffer)} bytes")
        except Exception as exc:
            print(f"[WARN] serial port closed: {port_name} ({exc})")
            time.sleep(SERIAL_REOPEN_DELAY_SEC)
        finally:
            self._close_serial_port(port_name)

    # ------------------------------------------------------------------
    # Payload mapping
    # ------------------------------------------------------------------
    def build_payload_from_frame(self, frame: ParsedFrame) -> dict[str, Any]:
        total_seed = round2(sum(frame.channel_values))
        has_alarm = any(value == 1 for value in frame.alarm_channels)

        # 当前串口协议没有单独给出“无种子”信号，避免用累计播种量做错误推断。
        has_no_seed = False

        telemetry = {
            "seed_channels_g": frame.channel_values,
            "seed_total_g": total_seed,
            "distance_m": frame.distance_m,
            "leak_distance_m": frame.leak_distance_m,
            "speed_kmh": frame.speed_kmh,
            "uniformity_index": frame.uniformity_index,
            "alarm_channels": frame.alarm_channels,
            "alarm_blocked": has_alarm,
            "alarm_no_seed": has_no_seed,
        }
        gps = {"lon": frame.lon, "lat": frame.lat}
        return {
            "ts": frame.received_at.isoformat(),
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
                            name="serial-reader",
                        )
                        self.reader_thread.start()
                    else:
                        print("[WARN] no serial port detected, rescanning...")

            try:
                port_name, frame = self.frame_queue.get(timeout=0.5)
            except queue.Empty:
                if self.current_run_id and self.last_valid_frame_at:
                    if time.time() - self.last_valid_frame_at >= RUN_IDLE_STOP_SEC:
                        self._finish_current_run("idle timeout")
                continue

            self.last_valid_frame_at = time.time()
            self.valid_frame_counter += 1

            debug_log(
                f"received frame from {port_name}: channels={frame.channel_values}, "
                f"speed={frame.speed_kmh}, dist={frame.distance_m}, lat={frame.lat}, lon={frame.lon}"
            )

            payload = self.build_payload_from_frame(frame)

            if not self.current_run_id and self.valid_frame_counter >= SERIAL_STABLE_FRAME_COUNT:
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
                            "channels": frame.channel_values,
                            "speed_kmh": frame.speed_kmh,
                            "distance_m": frame.distance_m,
                            "uniformity_index": frame.uniformity_index,
                            "gps": {"lat": frame.lat, "lon": frame.lon},
                            "alarms": frame.alarm_channels,
                            "total_seed": sum(frame.channel_values),
                            "has_alarm": any(value == 1 for value in frame.alarm_channels),
                            "has_no_seed": False,
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

        self.shutdown()

    def shutdown(self) -> None:
        self.stop_event.set()
        if self.current_run_id:
            self._finish_current_run("bridge shutdown")
        self._close_serial_port()
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=2.0)
        self.reader_thread = None


def sample_frame_bytes() -> bytes:
    return bytes(int(part, 16) for line in SAMPLE_FRAME_HEX_LINES for part in line.split())


def run_self_check() -> None:
    print("[CHECK] 开始执行串口协议自检")

    sample = sample_frame_bytes()
    frame = parse_frame(sample)
    assert validate_frame(frame)
    assert frame.channel_values == [23.22, 24.53, 26.17, 23.91, 24.03]
    assert frame.speed_kmh == 0.0
    assert frame.distance_m == 10.01
    assert frame.lat == 42.83
    assert frame.lon == 89.3
    assert frame.leak_distance_m == 1.25
    assert frame.uniformity_index == 0.0
    assert frame.alarm_channels == [0, 0, 0, 0, 0]
    print("[CHECK] 样例字节序解析通过")

    # 测试 payload 构建
    bridge = SerialIngestBridge(CloudConfig())
    payload = bridge.build_payload_from_frame(frame)
    assert payload["telemetry"]["seed_channels_g"] == [23.22, 24.53, 26.17, 23.91, 24.03]
    assert payload["telemetry"]["seed_total_g"] == 121.86
    assert payload["telemetry"]["alarm_no_seed"] is False
    print("[CHECK] payload 构建通过")

    assembler = SerialFrameAssembler()
    assembler.append(sample[:20])
    assert len(assembler.pop_frames()) == 0
    assembler.append(sample[20:])
    assert len(assembler.pop_frames()) == 1
    print("[CHECK] 半包组帧通过")

    assembler = SerialFrameAssembler()
    assembler.append(sample + sample)
    assert len(assembler.pop_frames()) == 2
    print("[CHECK] 粘包组帧通过")

    assembler = SerialFrameAssembler()
    assembler.append(b"\x00\x01\x02" + sample)
    assert len(assembler.pop_frames()) == 1
    print("[CHECK] 脏数据重同步通过")

    print("[CHECK] 全部通过")


def install_signal_handlers(bridge: SerialIngestBridge) -> None:
    def _handle_stop(signum: int, frame: Any) -> None:
        print(f"\n[INFO] stopping bridge, signal={signum}")
        bridge.stop_event.set()

    signal.signal(signal.SIGINT, _handle_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_stop)


def main() -> int:
    args = parse_args()
    if args.self_check:
        run_self_check()
        return 0

    bridge = SerialIngestBridge(CloudConfig(), preferred_port=args.port)
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
