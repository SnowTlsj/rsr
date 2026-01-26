# 播种监测系统 API 文档

**版本**: v1  
**更新时间**: 2026-01-07  
**Base URL**: `http://{host}:{port}/api/v1`  
**WebSocket URL**: `ws://{host}:{port}/ws/live`

---

## 目录

1. [认证方式](#认证方式)
2. [任务管理 API](#任务管理-api)
3. [数据上报 API](#数据上报-api)
4. [数据查询 API](#数据查询-api)
5. [WebSocket 实时数据](#websocket-实时数据)
6. [数据库表结构](#数据库表结构)
7. [数据流程说明](#数据流程说明)

---

## 认证方式

- **数据上报接口** (`/ingest`): 需要 Bearer Token 认证
- **其他接口**: 无需认证

**认证头格式**:

```
Authorization: Bearer {token}
```

**默认 Token**: `devtoken` (在 `.env` 中配置 `INGEST_TOKEN`)

---

## 任务管理 API

### 1. 创建/获取任务

**接口**: `POST /runs/start`

**功能**:

- 如果该 `machine_id` 已有活跃任务（`ended_at` 为 NULL），返回现有任务
- 如果没有活跃任务，创建新任务
- **保证同一 machine_id 同时只有一个活跃任务**

**请求体**:

```json
{
  "machine_id": "machine-001"
}
```

**响应** (200 OK):

```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "run_name": "Run machine-001 20260107-132100",
  "started_at": "2026-01-07T05:21:00Z"
}
```

**字段说明**:
| 字段 | 类型 | 说明 |
|------|------|------|
| machine_id | string | 设备 ID，用于标识设备 |
| run_id | UUID | 任务唯一标识符 |
| run_name | string | 任务名称（自动生成） |
| started_at | datetime | 任务开始时间 (UTC) |

---

### 2. 停止任务

**接口**: `POST /runs/{run_id}/stop`

**功能**: 结束指定任务，设置 `ended_at` 时间

**路径参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| run_id | UUID | 任务 ID |

**响应** (200 OK):

```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "ended_at": "2026-01-07T06:30:00Z"
}
```

**错误响应**:

- `404 Not Found`: 任务不存在

---

### 3. 获取任务列表

**接口**: `GET /runs`

**功能**: 查询最近的任务列表，支持按设备 ID 和时间范围过滤

**查询参数**:
| 参数 | 类型 | 默认值 | 范围 | 说明 |
|------|------|--------|------|------|
| days | int | 30 | 1-365 | 查询最近 N 天的任务 |
| machine_id | string | 可选 | - | 按设备 ID 过滤 |

**示例请求**:

```
GET /runs?days=7&machine_id=machine-001
```

**响应** (200 OK):

```json
[
  {
    "run_id": "550e8400-e29b-41d4-a716-446655440000",
    "machine_id": "machine-001",
    "run_name": "Run machine-001 20260107-132100",
    "started_at": "2026-01-07T05:21:00Z",
    "ended_at": null
  },
  {
    "run_id": "660e8400-e29b-41d4-a716-446655440001",
    "machine_id": "machine-001",
    "run_name": "Run machine-001 20260106-093000",
    "started_at": "2026-01-06T01:30:00Z",
    "ended_at": "2026-01-06T03:45:00Z"
  }
]
```

**字段说明**:

- `ended_at` 为 `null` 表示任务仍在进行中
- 结果按 `started_at` 降序排列（最新的在前）

---

### 4. 获取单个任务详情

**接口**: `GET /runs/{run_id}`

**功能**: 获取指定任务的详细信息

**路径参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| run_id | UUID | 任务 ID |

**响应** (200 OK):

```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "machine_id": "machine-001",
  "run_name": "Run machine-001 20260107-132100",
  "started_at": "2026-01-07T05:21:00Z",
  "ended_at": null
}
```

**错误响应**:

- `404 Not Found`: 任务不存在

---

### 5. 删除任务

**接口**: `DELETE /runs/{run_id}`

**功能**: 删除指定任务及其所有关联数据（GPS 点、遥测数据）

**路径参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| run_id | UUID | 任务 ID |

**响应** (204 No Content): 无响应体

**错误响应**:

- `404 Not Found`: 任务不存在

---

## 数据上报 API

### 上报播种和 GPS 数据

**接口**: `POST /ingest`

**功能**:

- 上报播种遥测数据和 GPS 位置数据
- 自动查找 `machine_id` 对应的活跃任务
- 数据会保存到数据库并实时广播到 WebSocket 客户端

**认证**: 需要 Bearer Token

**请求头**:

```
Authorization: Bearer devtoken
Content-Type: application/json
```

**请求体**:

```json
{
  "ts": "2026-01-07T05:21:00.123Z",
  "machine_id": "machine-001",
  "telemetry": {
    "seed_channels_g": [10.5, 11.2, 9.8, 10.1, 10.3],
    "seed_total_g": 51.9,
    "distance_m": 1500.5,
    "leak_distance_m": 12.3,
    "speed_kmh": 5.2,
    "alarm_channels": [0, 0, 1, 0, 0],
    "alarm_blocked": false,
    "alarm_no_seed": false
  },
  "gps": {
    "lon": 116.365,
    "lat": 40.0095,
    "alt_m": 50.0,
    "heading_deg": 90.0
  }
}
```

**字段说明**:

#### 根字段

| 字段       | 类型     | 必填 | 说明                       |
| ---------- | -------- | ---- | -------------------------- |
| ts         | datetime | ✅   | 数据时间戳 (ISO 8601 格式) |
| machine_id | string   | ✅   | 设备 ID                    |
| telemetry  | object   | 可选 | 播种遥测数据               |
| gps        | object   | 可选 | GPS 位置数据               |

#### telemetry 对象

| 字段            | 类型     | 说明                                   |
| --------------- | -------- | -------------------------------------- |
| seed_channels_g | float[5] | 5 个通道的播种量(克)，数组长度必须为 5 |
| seed_total_g    | float    | 总播种量(克)                           |
| distance_m      | float    | 累计里程(米)                           |
| leak_distance_m | float    | 漏播里程(米)                           |
| speed_kmh       | float    | 当前速度(km/h)                         |
| alarm_channels  | int[5]   | 5 个通道的警报状态，0=正常，1=警报     |
| alarm_blocked   | bool     | 堵塞警报                               |
| alarm_no_seed   | bool     | 缺种警报                               |

#### gps 对象

| 字段        | 类型  | 说明              |
| ----------- | ----- | ----------------- |
| lon         | float | 经度 (-180 ~ 180) |
| lat         | float | 纬度 (-90 ~ 90)   |
| alt_m       | float | 海拔(米)          |
| heading_deg | float | 航向角(度, 0-360) |

**响应** (202 Accepted):

```json
{
  "status": "queued"
}
```

**错误响应**:

- `401 Unauthorized`: 缺少认证令牌
- `403 Forbidden`: 认证令牌无效
- `409 Conflict`: 该 machine_id 没有活跃任务（需要先调用 `/runs/start`）

**数据处理流程**:

1. 验证认证令牌
2. 根据 `machine_id` 查找活跃任务的 `run_id`
3. 将 `seed_channels_g` 数组拆分为 `channel1_g` ~ `channel5_g`
4. 将 `alarm_channels` 数组拆分为 `alarm_channel1` ~ `alarm_channel5`
5. 数据入队，异步写入数据库
6. 实时广播到订阅该 `run_id` 的 WebSocket 客户端

---

## 数据查询 API

### 1. 获取 GPS 轨迹

**接口**: `GET /runs/{run_id}/gps`

**功能**: 获取指定任务的 GPS 轨迹点

**路径参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| run_id | UUID | 任务 ID |

**查询参数**:
| 参数 | 类型 | 默认值 | 范围 | 说明 |
|------|------|--------|------|------|
| limit | int | 100000 | 1-200000 | 返回的最大点数 |

**示例请求**:

```
GET /runs/550e8400-e29b-41d4-a716-446655440000/gps?limit=10000
```

**响应** (200 OK):

```json
[
  {
    "ts": "2026-01-07T05:21:00Z",
    "lon": 116.365,
    "lat": 40.0095,
    "alt_m": 50.0,
    "heading_deg": 90.0
  },
  {
    "ts": "2026-01-07T05:21:01Z",
    "lon": 116.36501,
    "lat": 40.00951,
    "alt_m": 50.1,
    "heading_deg": 91.0
  }
]
```

**说明**:

- 结果按时间戳升序排列
- 用于绘制 GPS 轨迹和导出数据

---

### 2. 获取播种遥测数据

**接口**: `GET /runs/{run_id}/telemetry`

**功能**: 获取指定任务的播种遥测数据，支持时间聚合

**路径参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| run_id | UUID | 任务 ID |

**查询参数**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| bucket | string | "1s" | 聚合时间窗口: "1s", "10s", "1m", "5m", "1h" |
| from | datetime | 可选 | 开始时间 (ISO 8601) |
| to | datetime | 可选 | 结束时间 (ISO 8601) |

**示例请求**:

```
GET /runs/550e8400-e29b-41d4-a716-446655440000/telemetry?bucket=1s
```

**响应** (200 OK):

```json
[
  {
    "ts": "2026-01-07T05:21:00Z",
    "channel1_g": 10.5,
    "channel2_g": 11.2,
    "channel3_g": 9.8,
    "channel4_g": 10.1,
    "channel5_g": 10.3,
    "seed_total_g": 51.9,
    "distance_m": 1500.5,
    "leak_distance_m": 12.3,
    "speed_kmh": 5.2,
    "alarm_blocked": false,
    "alarm_no_seed": false,
    "alarm_channel1": 0,
    "alarm_channel2": 0,
    "alarm_channel3": 1,
    "alarm_channel4": 0,
    "alarm_channel5": 0
  }
]
```

**聚合说明**:

- 数值字段（channel1_g ~ channel5_g, distance_m 等）使用 **平均值**
- 布尔字段（alarm_blocked, alarm_no_seed）使用 **逻辑或** (任一为 true 则为 true)
- 警报通道（alarm_channel1 ~ alarm_channel5）使用 **最大值**

---

## WebSocket 实时数据

### 连接 WebSocket

**URL**: `ws://{host}:{port}/ws/live?run_id={run_id}`

**功能**: 订阅指定任务的实时数据推送

**示例**:

```
ws://localhost:8200/ws/live?run_id=550e8400-e29b-41d4-a716-446655440000
```

**连接流程**:

1. 客户端连接 WebSocket，指定 `run_id`
2. 服务器将客户端加入该 `run_id` 的订阅列表
3. 当有新数据通过 `/ingest` 上报时，服务器自动推送到所有订阅的客户端
4. 每 5 秒发送一次心跳消息

---

### 消息格式

#### 1. 遥测数据消息

```json
{
  "type": "telemetry",
  "data": {
    "ts": "2026-01-07T05:21:00.123Z",
    "seed_channels_g": [10.5, 11.2, 9.8, 10.1, 10.3],
    "seed_total_g": 51.9,
    "distance_m": 1500.5,
    "leak_distance_m": 12.3,
    "speed_kmh": 5.2,
    "alarm_channels": [0, 0, 1, 0, 0],
    "alarm_blocked": false,
    "alarm_no_seed": false
  }
}
```

**推送频率**: 默认 10 Hz (可在 `.env` 中配置 `TELEMETRY_PUSH_HZ`)

---

#### 2. GPS 数据消息

```json
{
  "type": "gps",
  "data": {
    "ts": "2026-01-07T05:21:00.123Z",
    "lon": 116.365,
    "lat": 40.0095,
    "alt_m": 50.0,
    "heading_deg": 90.0
  }
}
```

**推送频率**: 默认 1 Hz (可在 `.env` 中配置 `GPS_PUSH_HZ`)

---

#### 3. 心跳消息

```json
{
  "type": "heartbeat",
  "ts": 1736234460.123
}
```

**推送频率**: 每 5 秒一次

**说明**: 客户端应忽略心跳消息，仅用于保持连接活跃

---

### 前端示例代码

```javascript
const ws = new WebSocket(`ws://localhost:8200/ws/live?run_id=${runId}`);

ws.onopen = () => {
  console.log("WebSocket connected");
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);

  if (message.type === "heartbeat") {
    // 忽略心跳消息
    return;
  }

  if (message.type === "telemetry") {
    const data = message.data;
    console.log("Telemetry:", data.seed_channels_g, data.speed_kmh);
    // 更新界面显示
  }

  if (message.type === "gps") {
    const data = message.data;
    console.log("GPS:", data.lon, data.lat);
    // 更新地图标记
  }
};

ws.onerror = (error) => {
  console.error("WebSocket error:", error);
};

ws.onclose = () => {
  console.log("WebSocket closed");
  // 可以实现自动重连逻辑
};
```

---

## 数据库表结构

### 1. runs 表

播种任务表，记录每次播种作业的基本信息

| 字段       | 类型         | 约束            | 说明                   |
| ---------- | ------------ | --------------- | ---------------------- |
| id         | UUID         | PRIMARY KEY     | 任务唯一标识符         |
| machine_id | VARCHAR(255) | NOT NULL, INDEX | 设备 ID                |
| run_name   | VARCHAR(255) | NOT NULL        | 任务名称               |
| started_at | TIMESTAMP    | NOT NULL, INDEX | 开始时间 (UTC)         |
| ended_at   | TIMESTAMP    | NULL, INDEX     | 结束时间 (NULL=进行中) |

**索引**:

- `idx_runs_machine_id`: 按设备 ID 查询
- `idx_runs_started_at`: 按时间范围查询
- `idx_runs_ended_at`: 查询活跃任务 (WHERE ended_at IS NULL)

---

### 2. telemetry_samples 表

播种遥测数据表，记录每次上报的播种数据

| 字段            | 类型      | 约束                         | 说明              |
| --------------- | --------- | ---------------------------- | ----------------- |
| id              | BIGSERIAL | PRIMARY KEY                  | 自增主键          |
| run_id          | UUID      | NOT NULL, FOREIGN KEY, INDEX | 关联任务 ID       |
| ts              | TIMESTAMP | NOT NULL, INDEX              | 数据时间戳 (UTC)  |
| channel1_g      | FLOAT     | NULL                         | 通道 1 播种量(克) |
| channel2_g      | FLOAT     | NULL                         | 通道 2 播种量(克) |
| channel3_g      | FLOAT     | NULL                         | 通道 3 播种量(克) |
| channel4_g      | FLOAT     | NULL                         | 通道 4 播种量(克) |
| channel5_g      | FLOAT     | NULL                         | 通道 5 播种量(克) |
| seed_total_g    | FLOAT     | NULL                         | 总播种量(克)      |
| distance_m      | FLOAT     | NULL                         | 累计里程(米)      |
| leak_distance_m | FLOAT     | NULL                         | 漏播里程(米)      |
| speed_kmh       | FLOAT     | NULL                         | 速度(km/h)        |
| alarm_blocked   | BOOLEAN   | NULL                         | 堵塞警报          |
| alarm_no_seed   | BOOLEAN   | NULL                         | 缺种警报          |
| alarm_channel1  | INTEGER   | NULL                         | 通道 1 警报状态   |
| alarm_channel2  | INTEGER   | NULL                         | 通道 2 警报状态   |
| alarm_channel3  | INTEGER   | NULL                         | 通道 3 警报状态   |
| alarm_channel4  | INTEGER   | NULL                         | 通道 4 警报状态   |
| alarm_channel5  | INTEGER   | NULL                         | 通道 5 警报状态   |

**索引**:

- `idx_telemetry_run_id`: 按任务 ID 查询
- `idx_telemetry_ts`: 按时间范围查询

---

### 3. gps_points 表

GPS 轨迹点表，记录设备的位置信息

| 字段        | 类型      | 约束                         | 说明             |
| ----------- | --------- | ---------------------------- | ---------------- |
| id          | BIGSERIAL | PRIMARY KEY                  | 自增主键         |
| run_id      | UUID      | NOT NULL, FOREIGN KEY, INDEX | 关联任务 ID      |
| ts          | TIMESTAMP | NOT NULL, INDEX              | 数据时间戳 (UTC) |
| lon         | FLOAT     | NOT NULL                     | 经度             |
| lat         | FLOAT     | NOT NULL                     | 纬度             |
| alt_m       | FLOAT     | NULL                         | 海拔(米)         |
| heading_deg | FLOAT     | NULL                         | 航向角(度)       |

**索引**:

- `idx_gps_run_id`: 按任务 ID 查询
- `idx_gps_ts`: 按时间范围查询

---

## 数据流程说明

### 完整数据流程图

```
┌─────────────────┐
│  程序/网页端     │
│  调用 /runs/start│
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  后端检查 machine_id 是否有活跃任务      │
│  - 有: 返回现有 run_id                   │
│  - 无: 创建新任务，返回新 run_id         │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────┐         ┌──────────────────┐
│  程序端          │         │  网页端           │
│  发送数据        │         │  连接 WebSocket   │
│  POST /ingest   │         │  ws://...?run_id  │
└────────┬────────┘         └────────┬─────────┘
         │                           │
         │  machine_id               │  订阅 run_id
         ▼                           ▼
┌─────────────────────────────────────────┐
│  后端 /ingest API                        │
│  1. 验证 Token                           │
│  2. 根据 machine_id 查找活跃 run_id      │
│  3. 拆分数组字段到独立列                 │
│  4. 数据入队                             │
└────────┬────────────────────────────────┘
         │
         ├──────────────┬──────────────┐
         ▼              ▼              ▼
┌────────────┐  ┌──────────────┐  ┌──────────────┐
│ 数据库写入  │  │ WebSocket    │  │ 返回 202     │
│ (异步队列) │  │ 实时广播     │  │ Accepted     │
└────────────┘  └──────┬───────┘  └──────────────┘
                       │
                       ▼
                ┌──────────────┐
                │  网页端接收   │
                │  更新界面显示 │
                └──────────────┘
```

---

### 场景 1：程序先启动，网页后连接

**步骤**:

1. **程序调用** `POST /runs/start` (machine_id=machine-001)

   - 后端创建新任务，返回 `run_id=AAA`

2. **程序发送数据** `POST /ingest` (machine_id=machine-001)

   - 后端查找 machine-001 的活跃任务 → 找到 `run_id=AAA`
   - 数据保存到数据库，关联到 `run_id=AAA`
   - 广播到订阅 `run_id=AAA` 的 WebSocket 客户端（此时无客户端）

3. **网页打开**

   - 调用 `GET /runs?machine_id=machine-001` 查找活跃任务
   - 找到 `run_id=AAA`，`ended_at=null`
   - 连接 WebSocket: `ws://host/ws/live?run_id=AAA`

4. **程序继续发送数据**
   - 数据广播到 WebSocket
   - 网页实时接收并显示

**结果**: ✅ 程序和网页使用同一个任务 AAA

---

### 场景 2：网页先启动，程序后连接

**步骤**:

1. **网页调用** `POST /runs/start` (machine_id=machine-001)

   - 后端创建新任务，返回 `run_id=BBB`
   - 网页连接 WebSocket: `ws://host/ws/live?run_id=BBB`

2. **程序启动**

   - 调用 `GET /runs?machine_id=machine-001` 查找活跃任务
   - 找到 `run_id=BBB`，`ended_at=null`
   - 使用 `run_id=BBB`（不创建新任务）

3. **程序发送数据** `POST /ingest` (machine_id=machine-001)
   - 后端查找 machine-001 的活跃任务 → 找到 `run_id=BBB`
   - 数据保存并广播到 WebSocket
   - 网页实时接收并显示

**结果**: ✅ 程序和网页使用同一个任务 BBB

---

### 场景 3：刷新网页不创建新任务

**步骤**:

1. **已有活跃任务** `run_id=CCC` (machine_id=machine-001)

2. **网页刷新**

   - localStorage 中保存了 `run_id=CCC`
   - 调用 `GET /runs/CCC` 验证任务是否仍活跃
   - 如果 `ended_at=null`，直接连接 WebSocket
   - 如果任务已结束，清除 localStorage，查找新的活跃任务

3. **如果没有 localStorage**
   - 调用 `GET /runs?machine_id=machine-001` 查找活跃任务
   - 找到 `run_id=CCC`，连接 WebSocket

**结果**: ✅ 刷新页面不会创建新任务

---

### 关键设计原则

#### 1. 单一活跃任务原则

**规则**: 同一 `machine_id` 同时只能有一个活跃任务（`ended_at IS NULL`）

**实现**:

- `POST /runs/start` 会先检查是否有活跃任务
- 有则返回现有任务，无则创建新任务
- 保证不会重复创建任务

#### 2. machine_id 关联原则

**规则**: 数据上报使用 `machine_id`，自动关联到活跃任务

**实现**:

- `POST /ingest` 接收 `machine_id`
- 后端查询 `SELECT id FROM runs WHERE machine_id=? AND ended_at IS NULL`
- 找到 `run_id` 后保存数据

**优点**:

- 程序端不需要知道 `run_id`
- 自动关联到正确的任务
- 避免 run_id 不一致的问题

#### 3. WebSocket 订阅原则

**规则**: WebSocket 订阅特定 `run_id` 的数据

**实现**:

- 客户端连接时指定 `run_id`
- 服务器维护 `run_id → WebSocket客户端集合` 的映射
- 数据广播时，只推送给订阅该 `run_id` 的客户端

**优点**:

- 支持多个任务同时运行
- 客户端只接收自己关心的数据

---

## 常见问题 FAQ

### Q1: 如何确保程序和网页使用同一个任务？

**A**: 通过 `machine_id` 关联：

- 程序和网页使用相同的 `machine_id`
- `/runs/start` 保证同一 `machine_id` 只有一个活跃任务
- `/ingest` 自动查找 `machine_id` 对应的活跃任务

### Q2: 如果程序发送数据时没有活跃任务怎么办？

**A**: `/ingest` 会返回 `409 Conflict` 错误。程序应该：

1. 先调用 `POST /runs/start` 创建任务
2. 再发送数据

### Q3: 网页刷新后数据会丢失吗？

**A**: 不会。数据保存在数据库中，可以通过以下方式查询：

- `GET /runs/{run_id}/telemetry` 查询历史遥测数据
- `GET /runs/{run_id}/gps` 查询历史 GPS 轨迹

### Q4: WebSocket 断开后如何重连？

**A**: 前端应实现自动重连逻辑：

```javascript
class ReconnectingWebSocket {
  connect() {
    this.ws = new WebSocket(this.url);
    this.ws.onclose = () => {
      setTimeout(() => this.connect(), 3000); // 3秒后重连
    };
  }
}
```

### Q5: 如何停止任务？

**A**: 调用 `POST /runs/{run_id}/stop`，会设置 `ended_at` 时间。之后：

- `/ingest` 不再接受该 `machine_id` 的数据（返回 409）
- 需要重新调用 `/runs/start` 创建新任务

### Q6: 数据上报频率有限制吗？

**A**:

- 建议频率: 10 Hz (每秒 10 次)
- 系统支持更高频率，但会增加数据库和网络负载
- WebSocket 推送频率可在 `.env` 中配置

---

## 配置说明

### 环境变量 (.env)

```bash
# 数据库配置
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/dbname

# 认证令牌
INGEST_TOKEN=devtoken

# WebSocket 推送频率
TELEMETRY_PUSH_HZ=10  # 遥测数据推送频率 (Hz)
GPS_PUSH_HZ=1         # GPS数据推送频率 (Hz)

# 默认坐标（前端使用）
VITE_DEFAULT_LONGITUDE=116.365
VITE_DEFAULT_LATITUDE=40.0095

# 设备ID（前端使用）
VITE_MACHINE_ID=machine-001
```

---

## 总结

本系统通过 **machine_id** 作为关联键，实现了程序端和网页端的数据统一：

1. **任务创建**: `/runs/start` 保证同一 machine_id 只有一个活跃任务
2. **数据上报**: `/ingest` 使用 machine_id 自动关联到活跃任务
3. **实时推送**: WebSocket 订阅 run_id，接收实时数据
4. **状态持久化**: 前端使用 localStorage 保存 run_id，刷新不丢失

**核心优势**:

- ✅ 无需手动同步 run_id
- ✅ 自动处理任务关联
- ✅ 支持任意顺序启动（程序先或网页先）
- ✅ 刷新页面不创建新任务
- ✅ 数据实时同步，延迟低

---

**文档版本**: v1.0
**最后更新**: 2026-01-07
**维护者**: 播种监测系统开发团队
