# Seed Monitor Platform (Vue 3 + FastAPI + PostgreSQL)

面向播种作业的实时监控与历史回放平台，包含前端监控大屏、历史数据回放、任务管理、数据摄取与实时推送能力。支持 WebSocket 实时数据流、GPS 轨迹绘制、作业统计与报表导出。

## 主要特性

- 实时监控：WebSocket 推送播种通道、里程、速度、告警与 GPS 数据
- 任务管理：一键开始/停止播种任务，自动识别活跃任务
- 历史回放：按任务查看轨迹、统计信息、历史数据
- 数据摄取：统一 ingest 接口，支持 telemetry 与 GPS 分离上传
- 数据留存：仅保留最近 30 天 runs，后端定时清理
- 报表功能：历史页支持生成报告与导出（Excel/PDF）

## 技术栈

- 前端：Vue 3 + Vite + TypeScript + Pinia + ECharts
- 后端：FastAPI (async) + SQLAlchemy 2.x (async) + asyncpg
- 数据库：PostgreSQL / TimescaleDB
- 迁移：Alembic
- 部署：Docker Compose

## 快速开始

### 1. 环境配置

在项目根目录创建 `.env`：

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/seed_monitor
INGEST_TOKEN=devtoken
DB_BATCH_MAX_SIZE=500
DB_BATCH_MAX_LATENCY_MS=500
QUEUE_HIGH_WATERMARK=2000
TELEMETRY_PUSH_HZ=5
GPS_PUSH_HZ=1
RETENTION_DAYS=30
CORS_ALLOW_ORIGINS=*
```

在 `frontend/` 目录创建 `.env`：

```
VITE_API_BASE=http://your-host:8000/api/v1
VITE_WS_BASE=ws://your-host:8000
VITE_MACHINE_ID=machine-001
VITE_BAIDU_AK=your_baidu_ak
VITE_DEFAULT_LONGITUDE=116.3650
VITE_DEFAULT_LATITUDE=40.0095
```

### 2. 启动服务

```
docker compose up --build
```

### 3. 初始化数据库

```
docker compose exec backend alembic upgrade head
```

前端访问：`http://your-host:5174`

## 功能使用说明

### 实时监控（MonitorView）

- 点击“开始播种”创建任务并建立 WebSocket 连接
- 实时显示通道播种量、里程、速度、告警指示灯
- 实时更新地图位置与轨迹
- 点击“停止播种”结束任务
- “同步”按钮用于手动拉取当前活跃任务并重连

### 历史数据（HistoryView）

- 左侧显示最近 30 天的任务列表
- 点击任务后加载 GPS 轨迹并绘制地图
- 可生成报告并导出 Excel/PDF
- 支持删除任务（级联删除数据）

## API 文档

基础前缀：`/api/v1`

### 1) 开始任务

```
POST /api/v1/runs/start
Content-Type: application/json

{
  "machine_id": "machine-001"
}
```

响应：

```
{
  "run_id": "uuid",
  "run_name": "Run machine-001 20240101-120000",
  "started_at": "2024-01-01T12:00:00Z"
}
```

### 2) 停止任务

```
POST /api/v1/runs/{run_id}/stop
```

响应：

```
{
  "run_id": "uuid",
  "ended_at": "2024-01-01T12:30:00Z"
}
```

### 3) 获取任务列表

```
GET /api/v1/runs?days=30&machine_id=machine-001
```

响应：

```
[
  {
    "run_id": "uuid",
    "machine_id": "machine-001",
    "run_name": "Run ...",
    "started_at": "...",
    "ended_at": "..."
  }
]
```

### 4) 获取 GPS 点

```
GET /api/v1/runs/{run_id}/gps?limit=100000
```

响应：

```
[
  { "ts": "2024-01-01T12:00:00Z", "lon": 116.365, "lat": 40.0095 }
]
```

### 5) 获取 Telemetry（聚合）

```
GET /api/v1/runs/{run_id}/telemetry?from=2024-01-01T12:00:00Z&to=2024-01-01T12:10:00Z&bucket=1s
```

`bucket` 支持 `1s / 5s / 1m / 1h` 等。

### 6) 摄取数据（Ingest）

```
POST /api/v1/ingest
Authorization: Bearer <INGEST_TOKEN>
Content-Type: application/json

{
  "ts": "2024-01-01T12:00:00Z",
  "machine_id": "machine-001",
  "telemetry": {
    "seed_channels_g": [10.2, 9.8, 10.5, 9.9, 10.1],
    "seed_total_g": 50.5,
    "distance_m": 120.4,
    "leak_distance_m": 1.2,
    "speed_kmh": 4.2,
    "uniformity_index": 92.5,
    "alarm_channels": [0,0,0,0,0],
    "alarm_blocked": false,
    "alarm_no_seed": false
  },
  "gps": {
    "lon": 116.365,
    "lat": 40.0095
  }
}
```

响应：`202 Accepted`

### 7) WebSocket 实时推送

```
/ws/live?run_id=<run_id>
```

推送消息示例：

```
{ "type": "telemetry", "data": { ... } }
{ "type": "gps", "data": { ... } }
```

## 目录结构说明

```
backend/
  app/
    api/            # API 路由
    core/           # 配置
    db/             # 数据库模型/会话
    services/       # ingest 队列、广播等服务
    main.py         # FastAPI 启动入口
  migrations/       # Alembic 迁移
  requirements.txt  # 后端依赖
  Dockerfile        # 后端镜像构建

frontend/
  src/
    api/            # axios 与 WebSocket 封装
    assets/         # 静态资源与基础样式
    components/     # MonitorView / ReportModal 等
    views/          # HistoryView
    router/         # Vue Router
    stores/         # Pinia 状态
    types/          # 全局类型声明
    main.ts         # 前端入口
  index.html        # BMapGL 注入
  package.json
  vite.config.ts
  Dockerfile

Docker Compose & Root
  docker-compose.yml
  .env.example
  frontend/.env.example
```

## 数据库表说明

- `runs`：任务表
- `telemetry_samples`：播种通道及遥测数据
- `gps_points`：GPS 点序列

索引：

- `telemetry_samples(run_id, ts)`
- `gps_points(run_id, ts)`

## 数据留存策略

后端启动时创建后台任务，每 24 小时执行：

```
DELETE FROM runs WHERE started_at < now() - interval '30 days'
```

并级联删除 telemetry/gps。

## 部署建议

- 生产环境建议使用反向代理（Nginx）统一前后端入口
- 调整 `DB_BATCH_MAX_SIZE` 与 `DB_BATCH_MAX_LATENCY_MS` 以适配吞吐
- 建议配置 TimescaleDB 以优化时序查询

## FAQ

1. 前端无法显示地图？

   - 检查 `VITE_BAIDU_AK` 是否正确
   - 检查是否有广告屏蔽导致脚本被拦截

2. 历史数据加载失败？

   - 检查 `/api/v1/runs/{run_id}/gps` 返回是否 200
   - 检查数据库是否存在 GPS 数据

3. WebSocket 无法连接？

   - 确认 `VITE_WS_BASE` 与后端地址一致

## 许可证

内部项目，如需对外发布请补充 License 说明。
