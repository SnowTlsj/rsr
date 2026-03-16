# API 文档

## 1. 基础信息

- HTTP Base URL：`http://${API_HOST}:8100/api/v1`
- WebSocket URL：`ws://${API_HOST}:8100/ws/live?run_id={run_id}&token={ADMIN_TOKEN}`
- 数据格式：`application/json`
- 时间格式：ISO8601（UTC）

## 2. 鉴权模型

### Token 类型

- `ADMIN_TOKEN`
  - 任务管理、查询、报告、WebSocket
- `INGEST_TOKEN`
  - 数据上报

### 鉴权规则

- 除 `GET /healthz`、`GET /readyz` 外，业务接口均鉴权。
- HTTP：`Authorization: Bearer <TOKEN>`
- WebSocket：通过 query 参数 `token` 传入。

## 3. 接口总览

| 方法 | 路径 | 说明 | Token |
|---|---|---|---|
| POST | `/runs/start` | 启动或接入 active run | ADMIN |
| POST | `/runs/{run_id}/stop` | 停止任务 | ADMIN |
| GET | `/runs` | 查询任务列表 | ADMIN |
| GET | `/runs/{run_id}` | 查询任务详情 | ADMIN |
| DELETE | `/runs/{run_id}` | 删除任务与关联数据 | ADMIN |
| GET | `/runs/{run_id}/gps` | 查询 GPS 轨迹 | ADMIN |
| GET | `/runs/{run_id}/telemetry` | 查询聚合遥测序列 | ADMIN |
| GET | `/runs/{run_id}/report.pdf` | 下载 PDF 报告 | ADMIN |
| POST | `/ingest` | 写入 telemetry/gps（异步入队） | INGEST |

## 4. 运行任务接口

### 4.1 启动任务

`POST /runs/start`

请求头：

```http
Authorization: Bearer ${ADMIN_TOKEN}
Content-Type: application/json
```

请求体：

```json
{}
```

响应：

```json
{
  "run_id": "803e549d-3d94-4db9-9be6-0eba6a32ba04",
  "run_name": "Run 20260306-213000",
  "started_at": "2026-03-06T13:30:00.123456Z"
}
```

说明：

- 若存在 active run（`ended_at = null`），返回现有任务。
- 否则创建新任务。

### 4.2 停止任务

`POST /runs/{run_id}/stop`

响应：

```json
{
  "run_id": "803e549d-3d94-4db9-9be6-0eba6a32ba04",
  "ended_at": "2026-03-06T14:30:00.123456Z"
}
```

### 4.3 列表查询

`GET /runs?days=30`

参数：

- `days`：`1 ~ 365`，默认 `30`

响应：

```json
[
  {
    "run_id": "803e549d-3d94-4db9-9be6-0eba6a32ba04",
    "run_name": "Run 20260306-213000",
    "started_at": "2026-03-06T13:30:00.123456Z",
    "ended_at": null
  }
]
```

### 4.4 详情查询

`GET /runs/{run_id}`

### 4.5 删除任务

`DELETE /runs/{run_id}`

- 成功返回 `204 No Content`
- 级联删除 telemetry/gps 数据

## 5. 历史数据查询

### 5.1 GPS 查询

`GET /runs/{run_id}/gps?limit=100000`

参数：

- `limit`：`1 ~ 200000`，默认 `100000`

响应：

```json
[
  {
    "ts": "2026-03-06T13:30:10.100000Z",
    "lon": 116.365,
    "lat": 40.0095
  }
]
```

### 5.2 Telemetry 聚合查询

`GET /runs/{run_id}/telemetry?bucket=1s&from=...&to=...`

参数：

- `bucket`：聚合粒度，支持 `1s`、`10s`、`1m`、`1h` 等
- `from`：起始时间（可选）
- `to`：结束时间（可选）

聚合逻辑：

- 数值字段：`avg`
- `alarm_blocked`、`alarm_no_seed`：`bool_or`
- `alarm_channel1..5`：`max`

响应示例：

```json
[
  {
    "ts": "2026-03-06T13:30:10Z",
    "channel1_g": 9.8,
    "channel2_g": 10.1,
    "channel3_g": 9.9,
    "channel4_g": 10.2,
    "channel5_g": 9.7,
    "seed_total_g": 49.7,
    "distance_m": 123.4,
    "leak_distance_m": 1.2,
    "speed_kmh": 4.1,
    "uniformity_index": 0.40,
    "alarm_blocked": false,
    "alarm_no_seed": false,
    "alarm_channel1": 0,
    "alarm_channel2": 0,
    "alarm_channel3": 0,
    "alarm_channel4": 0,
    "alarm_channel5": 0
  }
]
```

### 5.3 PDF 报告

`GET /runs/{run_id}/report.pdf`

- 返回类型：`application/pdf`
- 文件名：`{run_name}.pdf`

## 6. 数据上报接口

### 6.1 上报数据

`POST /ingest`

请求头：

```http
Authorization: Bearer ${INGEST_TOKEN}
Content-Type: application/json
```

请求体：

```json
{
  "ts": "2026-03-06T13:30:30.123456Z",
  "telemetry": {
    "seed_channels_g": [10.1, 9.8, 10.3, 10.0, 9.9],
    "seed_total_g": 50.1,
    "distance_m": 120.5,
    "leak_distance_m": 1.2,
    "speed_kmh": 4.3,
    "uniformity_index": 0.42,
    "alarm_channels": [0, 0, 1, 0, 0],
    "alarm_blocked": true,
    "alarm_no_seed": false
  },
  "gps": {
    "lon": 116.365,
    "lat": 40.0095
  }
}
```

说明：

- `telemetry` 与 `gps` 可单独存在，也可同时上报。
- 服务端会写入当前 active run。
- 若不存在 active run，返回 `409`。
- 成功返回 `202`：

```json
{"status":"queued"}
```

## 7. WebSocket 实时订阅

`GET /ws/live?run_id={run_id}&token={ADMIN_TOKEN}`

消息类型：

### 7.1 telemetry

```json
{
  "type": "telemetry",
  "data": {
    "ts": "2026-03-06T13:30:30.123456+00:00",
    "seed_channels_g": [10, 10, 10, 10, 10],
    "distance_m": 120.5,
    "leak_distance_m": 1.2,
    "speed_kmh": 4.3,
    "alarm_channels": [0, 0, 0, 0, 0],
    "alarm_blocked": false,
    "alarm_no_seed": false
  }
}
```

### 7.2 gps

```json
{
  "type": "gps",
  "data": {
    "ts": "2026-03-06T13:30:30.123456+00:00",
    "lon": 116.365,
    "lat": 40.0095
  }
}
```

### 7.3 heartbeat

```json
{
  "type": "heartbeat",
  "ts": 1760000000.123
}
```

## 8. 错误码

| 状态码 | 含义 |
|---|---|
| `401` | 缺少或格式错误的 Authorization |
| `403` | Token 无效或权限不足 |
| `404` | run 不存在 |
| `409` | 无 active run（ingest 场景） |
| `422` | 参数/数据校验失败 |
| `500` | 服务内部错误 |

## 9. cURL 示例

### 9.1 启动任务

```bash
curl -X POST "http://${API_HOST}:8100/api/v1/runs/start" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{}"
```

### 9.2 上报数据

```bash
curl -X POST "http://${API_HOST}:8100/api/v1/ingest" \
  -H "Authorization: Bearer ${INGEST_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "ts": "2026-03-06T13:30:30.123456Z",
    "telemetry": {
      "seed_channels_g": [10.1, 9.8, 10.3, 10.0, 9.9],
      "distance_m": 120.5,
      "leak_distance_m": 1.2,
      "speed_kmh": 4.3,
      "alarm_channels": [0, 0, 0, 0, 0]
    },
    "gps": {"lon": 116.365, "lat": 40.0095}
  }'
```

### 9.3 停止任务

```bash
curl -X POST "http://${API_HOST}:8100/api/v1/runs/${RUN_ID}/stop" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"
```

## 10. 健康检查接口

- `GET /healthz`：返回 `{"status":"ok"}`
- `GET /readyz`：数据库连通性检查