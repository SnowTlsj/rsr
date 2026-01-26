#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
播种监测系统测试脚本
模拟设备上报数据，用于测试 API 接口

使用方法:
    python test_ingest.py                              # 自动创建新任务
    python test_ingest.py --run-id <uuid>              # 连接到现有任务
    python test_ingest.py --host 192.168.1.100 --port 8200

按 Ctrl+C 停止测试
"""

import argparse
import random
import time
import math
from datetime import datetime, timezone

import requests

# 默认配置
DEFAULT_HOST = "nas.tlsi.top"
DEFAULT_PORT = 8200
DEFAULT_TOKEN = "devtoken"
DEFAULT_MACHINE_ID = "machine-001"

# 默认 GPS 坐标（北京附近）
DEFAULT_LAT = 40.0095
DEFAULT_LON = 116.365

# 数据上报频率 (Hz)
INGEST_RATE = 10  # 每秒10次


def parse_args():
    parser = argparse.ArgumentParser(description="播种监测系统测试脚本")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"服务器地址 (默认: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"服务器端口 (默认: {DEFAULT_PORT})")
    parser.add_argument("--token", default=DEFAULT_TOKEN, help=f"认证令牌 (默认: {DEFAULT_TOKEN})")
    parser.add_argument("--machine-id", default=DEFAULT_MACHINE_ID, help=f"设备ID (默认: {DEFAULT_MACHINE_ID})")
    parser.add_argument("--run-id", help="连接到现有任务的 run_id (不指定则自动检测)")
    parser.add_argument("--mode", choices=["auto", "follow", "create"], default="auto",
                        help="运行模式: auto=自动选择, follow=仅跟随现有任务, create=强制创建新任务 (默认: auto)")
    return parser.parse_args()


def get_active_run(base_url: str, machine_id: str) -> str | None:
    """获取当前活跃的任务"""
    try:
        resp = requests.get(f"{base_url}/runs", params={"days": 1, "machine_id": machine_id})
        resp.raise_for_status()
        runs = resp.json()
        # 查找未结束的任务
        for run in runs:
            if run.get("ended_at") is None:
                return run["run_id"]
    except Exception as e:
        print(f"[WARN] 获取活跃任务失败: {e}")
    return None


def start_run(base_url: str, machine_id: str) -> str:
    """开始播种任务，返回 run_id"""
    resp = requests.post(f"{base_url}/runs/start", json={"machine_id": machine_id})
    resp.raise_for_status()
    data = resp.json()
    print(f"[INFO] 任务已创建: {data['run_name']}")
    print(f"[INFO] Run ID: {data['run_id']}")
    return data["run_id"]


def stop_run(base_url: str, run_id: str):
    """停止播种任务"""
    resp = requests.post(f"{base_url}/runs/{run_id}/stop")
    resp.raise_for_status()
    print(f"[INFO] 任务已停止: {run_id}")


def generate_seed_data():
    """生成随机播种数据 (5个通道，单位: g)"""
    return [round(random.uniform(8.0, 12.0), 2) for _ in range(5)]


def generate_alarm_data():
    """生成随机警报数据 (5个通道，0=正常，1=告警)"""
    # 10% 概率触发警报
    return [1 if random.random() < 0.1 else 0 for _ in range(5)]


def generate_gps_point(base_lat: float, base_lon: float, step: int):
    """生成 GPS 坐标点，模拟移动轨迹"""
    # 模拟蛇形移动轨迹
    angle = step * 0.05
    radius = 0.0005  # 约50米范围
    
    lat_offset = radius * math.sin(angle) + (step * 0.00001)  # 缓慢向北移动
    lon_offset = radius * math.cos(angle * 0.5)
    
    return round(base_lat + lat_offset, 6), round(base_lon + lon_offset, 6)


def send_data(base_url: str, token: str, machine_id: str, telemetry: dict, gps: dict):
    """发送数据到 ingest 接口"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "machine_id": machine_id,
        "telemetry": telemetry,
        "gps": gps
    }
    resp = requests.post(f"{base_url}/ingest", headers=headers, json=payload)
    return resp.status_code == 202


def main():
    args = parse_args()
    base_url = f"http://{args.host}:{args.port}/api/v1"

    print("=" * 60)
    print("播种监测系统测试脚本")
    print("=" * 60)
    print(f"服务器: {base_url}")
    print(f"设备ID: {args.machine_id}")
    print(f"运行模式: {args.mode}")
    print(f"上报频率: {INGEST_RATE} Hz")
    print("按 Ctrl+C 停止测试")
    print("=" * 60)

    # 确定使用的 run_id
    run_id = None
    auto_created = False

    if args.run_id:
        # 使用指定的 run_id
        run_id = args.run_id
        print(f"\n[INFO] 使用指定的任务: {run_id}")
    else:
        # 根据模式处理
        if args.mode == "follow":
            # 仅跟随模式：只查找现有任务，不创建
            print(f"\n[INFO] 跟随模式：查找现有任务...")
            run_id = get_active_run(base_url, args.machine_id)
            if run_id:
                print(f"[INFO] 找到活跃任务: {run_id}")
            else:
                print(f"[ERROR] 没有找到活跃任务，跟随模式下不创建新任务")
                print(f"[HINT] 请先在网页端创建任务，或使用 --mode auto")
                return

        elif args.mode == "create":
            # 强制创建模式：总是创建新任务（会先停止现有任务）
            print(f"\n[INFO] 创建模式：强制创建新任务...")
            existing_run_id = get_active_run(base_url, args.machine_id)
            if existing_run_id:
                print(f"[WARN] 发现现有任务: {existing_run_id}，将被停止")
                # 这里可以添加停止任务的逻辑
            try:
                run_id = start_run(base_url, args.machine_id)
                auto_created = True
            except Exception as e:
                print(f"[ERROR] 无法创建任务: {e}")
                return

        else:  # auto 模式
            # 自动模式：先查找，没有则创建
            print(f"\n[INFO] 自动模式：查找或创建任务...")
            run_id = get_active_run(base_url, args.machine_id)
            if run_id:
                print(f"[INFO] 找到活跃任务: {run_id}")
                print(f"[INFO] 自动使用此任务")
            else:
                print(f"[INFO] 没有活跃任务，创建新任务...")
                try:
                    run_id = start_run(base_url, args.machine_id)
                    auto_created = True
                except Exception as e:
                    print(f"[ERROR] 无法创建任务: {e}")
                    return

    # 初始化状态
    step = 0
    distance = 0.0
    leak_distance = 0.0
    success_count = 0
    error_count = 0
    interval = 1.0 / INGEST_RATE

    try:
        print("\n[INFO] 开始发送数据...")
        print(f"[INFO] 目标任务: {run_id}")
        print("-" * 60)

        last_log_time = time.time()
        log_interval = 5  # 每5秒输出一次统计

        while True:
            start_time = time.time()

            # 生成数据
            seed_channels = generate_seed_data()
            alarm_channels = generate_alarm_data()
            lat, lon = generate_gps_point(DEFAULT_LAT, DEFAULT_LON, step)

            # 模拟速度和里程
            speed = round(random.uniform(3.0, 6.0), 1)
            distance += speed / 3.6 / INGEST_RATE  # 转换为米
            if random.random() < 0.05:  # 5% 概率漏播
                leak_distance += speed / 3.6 / INGEST_RATE

            telemetry = {
                "seed_channels_g": seed_channels,
                "speed_kmh": speed,
                "distance_m": round(distance, 2),
                "leak_distance_m": round(leak_distance, 2),
                "alarm_channels": alarm_channels
            }
            gps = {"lat": lat, "lon": lon}

            # 发送数据
            if send_data(base_url, args.token, args.machine_id, telemetry, gps):
                success_count += 1
            else:
                error_count += 1
                print(f"[ERROR] 数据发送失败 (错误计数: {error_count})")

            step += 1

            # 定期输出统计信息
            current_time = time.time()
            if current_time - last_log_time >= log_interval:
                total = success_count + error_count
                success_rate = (success_count / total * 100) if total > 0 else 0
                alarm_str = "".join(["!" if a else "." for a in alarm_channels])
                print(f"[STATS] 已发送: {total} | 成功: {success_count} | 失败: {error_count} | 成功率: {success_rate:.1f}%")
                print(f"[DATA]  里程: {distance:.1f}m | 漏播: {leak_distance:.1f}m | 速度: {speed:.1f}km/h | 警报: [{alarm_str}]")
                last_log_time = current_time

            # 控制发送频率
            elapsed = time.time() - start_time
            if elapsed < interval:
                time.sleep(interval - elapsed)

    except KeyboardInterrupt:
        print("\n\n[INFO] 收到停止信号...")
    finally:
        # 只有自动创建的任务才自动停止
        if auto_created:
            try:
                stop_run(base_url, run_id)
            except Exception as e:
                print(f"[ERROR] 停止任务失败: {e}")
        else:
            print(f"[INFO] 任务 {run_id} 未自动停止（请在前端手动停止）")

        print("\n" + "=" * 50)
        print("测试统计")
        print("=" * 50)
        print(f"总发送次数: {step}")
        print(f"成功: {success_count}")
        print(f"失败: {error_count}")
        print(f"总里程: {distance:.2f} m")
        print(f"漏播里程: {leak_distance:.2f} m")
        print("=" * 50)


if __name__ == "__main__":
    main()

