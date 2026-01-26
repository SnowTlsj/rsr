#!/usr/bin/env python3
"""
快速测试脚本 - 验证播种监测系统功能
用于快速验证系统的各项功能是否正常
"""

import requests
import time
import sys

# 配置
API_BASE = "http://nas.tlsi.top:8200/api/v1"
MACHINE_ID = "machine-001"
TOKEN = "devtoken"

def print_header(title):
    """打印测试标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def print_result(test_name, success, message=""):
    """打印测试结果"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} | {test_name}")
    if message:
        print(f"     └─ {message}")

def test_backend_health():
    """测试1: 后端健康检查"""
    print_header("测试1: 后端健康检查")
    try:
        response = requests.get(f"{API_BASE}/runs", timeout=5)
        success = response.status_code == 200
        print_result("后端API可访问", success, f"状态码: {response.status_code}")
        return success
    except Exception as e:
        print_result("后端API可访问", False, f"错误: {e}")
        return False

def test_create_run():
    """测试2: 创建任务"""
    print_header("测试2: 创建任务")
    try:
        response = requests.post(
            f"{API_BASE}/runs/start",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json={"machine_id": MACHINE_ID, "run_name": "快速测试任务"}
        )
        success = response.status_code == 200
        if success:
            data = response.json()
            run_id = data.get("run_id")
            is_new = data.get("is_new", False)
            status = "新建" if is_new else "已存在"
            print_result("创建任务", True, f"任务ID: {run_id[:8]}... ({status})")
            return run_id
        else:
            print_result("创建任务", False, f"状态码: {response.status_code}")
            return None
    except Exception as e:
        print_result("创建任务", False, f"错误: {e}")
        return None

def test_get_active_run(run_id):
    """测试3: 查询活跃任务"""
    print_header("测试3: 查询活跃任务")
    try:
        response = requests.get(
            f"{API_BASE}/runs",
            params={"machine_id": MACHINE_ID, "days": 1}
        )
        success = response.status_code == 200
        if success:
            runs = response.json()
            active_runs = [r for r in runs if not r.get("ended_at")]
            if active_runs:
                found_run = active_runs[0]
                match = found_run["run_id"] == run_id
                print_result("查询活跃任务", True, 
                           f"找到 {len(active_runs)} 个活跃任务")
                print_result("任务ID匹配", match, 
                           f"期望: {run_id[:8]}..., 实际: {found_run['run_id'][:8]}...")
                return match
            else:
                print_result("查询活跃任务", False, "没有找到活跃任务")
                return False
        else:
            print_result("查询活跃任务", False, f"状态码: {response.status_code}")
            return False
    except Exception as e:
        print_result("查询活跃任务", False, f"错误: {e}")
        return False

def test_ingest_data(run_id):
    """测试4: 发送数据"""
    print_header("测试4: 发送数据")
    try:
        payload = {
            "machine_id": MACHINE_ID,
            "telemetry": {
                "seed_channels_g": [10.5, 11.2, 9.8, 10.1, 10.9],
                "speed_kmh": 5.0,
                "distance_m": 100.0,
                "leak_distance_m": 5.0,
                "alarm_channels": [False, False, False, False, False]
            },
            "gps": {
                "lat": 40.0095,
                "lon": 116.3650
            }
        }
        
        response = requests.post(
            f"{API_BASE}/ingest",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json=payload
        )
        success = response.status_code == 200
        print_result("发送数据", success, f"状态码: {response.status_code}")
        return success
    except Exception as e:
        print_result("发送数据", False, f"错误: {e}")
        return False

def test_get_run_detail(run_id):
    """测试5: 查询任务详情"""
    print_header("测试5: 查询任务详情")
    try:
        response = requests.get(f"{API_BASE}/runs/{run_id}")
        success = response.status_code == 200
        if success:
            run = response.json()
            print_result("查询任务详情", True, f"任务名称: {run.get('run_name')}")
            print_result("任务状态", not run.get("ended_at"), 
                       "活跃" if not run.get("ended_at") else "已结束")
            return True
        else:
            print_result("查询任务详情", False, f"状态码: {response.status_code}")
            return False
    except Exception as e:
        print_result("查询任务详情", False, f"错误: {e}")
        return False

def main():
    """主测试流程"""
    print("\n" + "🚀" * 30)
    print("播种监测系统 - 快速测试")
    print("🚀" * 30)
    print(f"\n配置:")
    print(f"  API地址: {API_BASE}")
    print(f"  设备ID: {MACHINE_ID}")
    
    results = []
    
    # 测试1: 后端健康检查
    results.append(("后端健康检查", test_backend_health()))
    if not results[-1][1]:
        print("\n❌ 后端服务不可用，测试终止")
        sys.exit(1)
    
    # 测试2: 创建任务
    run_id = test_create_run()
    results.append(("创建任务", run_id is not None))
    if not run_id:
        print("\n❌ 无法创建任务，测试终止")
        sys.exit(1)
    
    # 测试3: 查询活跃任务
    results.append(("查询活跃任务", test_get_active_run(run_id)))
    
    # 测试4: 发送数据
    results.append(("发送数据", test_ingest_data(run_id)))
    
    # 测试5: 查询任务详情
    results.append(("查询任务详情", test_get_run_detail(run_id)))
    
    # 汇总结果
    print_header("测试汇总")
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {test_name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！系统运行正常。")
        print("\n下一步:")
        print("  1. 运行 'python test_ingest.py' 开始持续发送数据")
        print("  2. 打开浏览器访问 http://localhost:8200")
        print("  3. 查看实时数据更新")
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查系统配置")
        sys.exit(1)

if __name__ == "__main__":
    main()

