# RSR 播种监测系统

RSR 是一个可部署的前后端一体化播种监测项目，提供实时监控、历史轨迹回放、报表导出与数据上报能力。

- 前端：Vue 3 + Vite + TypeScript + Pinia + ECharts + 百度地图 BMapGL
- 后端：FastAPI + SQLAlchemy Async + Alembic + PostgreSQL/TimescaleDB
- 部署：Docker Compose

## 核心能力

- 监控页（`/`）
  - 开始/停止任务
  - 实时显示 5 通道播种量、总播种量、里程、漏播、速度、匀播指数
  - WebSocket 连接状态、心跳状态、断线重连
  - 地图实时定位和轨迹
- 历史页（`/history`）
  - 最近 30 天任务列表
  - 轨迹回放（优先 `PointCollection`）
  - 报告查看、PDF 导出、Excel 导出、记录删除
- 数据链路
  - `/ingest` 快速入队（`202`）
  - 后台异步批量写库 + 高水位背压聚合
  - 按 `run_id` 广播 telemetry/gps
  - 每日清理 30 天前数据

## 鉴权与安全基线

系统使用 Bearer Token 双令牌模型：

- `ADMIN_TOKEN`
  - 用于任务管理、历史查询、报告导出、WebSocket 订阅
  - 覆盖 `/runs*`、`/report.pdf`、`/ws/live`
- `INGEST_TOKEN`
  - 仅用于 `POST /api/v1/ingest`

除 `GET /healthz` 与 `GET /readyz` 外，其它业务接口均要求鉴权。

## 快速启动（Docker）

1. 复制配置文件

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

2. 按实际环境修改 `.env` 与 `frontend/.env`

3. 启动服务

```bash
docker compose up -d --build
```

4. 访问地址（按你的端口映射）

- 前端：`http://${FRONTEND_HOST}:5174`
- 后端：`http://${API_HOST}:8100`
- 数据库：`${DB_HOST}:5433`

5. 查看日志

```bash
docker compose logs -f backend
docker compose logs -f frontend
```

## 环境变量

### 后端 `.env`

| 变量 | 说明 | 示例 |
|---|---|---|
| `DATABASE_URL` | 异步数据库连接串 | `postgresql+asyncpg://postgres:postgres@db:5432/seed_monitor` |
| `ADMIN_TOKEN` | 管理接口鉴权令牌 | `change-me-admin-token` |
| `INGEST_TOKEN` | 数据上报鉴权令牌 | `change-me-ingest-token` |
| `DB_BATCH_MAX_SIZE` | 批量写入条数阈值 | `500` |
| `DB_BATCH_MAX_LATENCY_MS` | 批量写入时间阈值（毫秒） | `500` |
| `QUEUE_HIGH_WATERMARK` | 高水位，超过后启用聚合背压 | `2000` |
| `TELEMETRY_PUSH_HZ` | telemetry 推送频率 | `5` |
| `GPS_PUSH_HZ` | gps 推送频率 | `1` |
| `RETENTION_DAYS` | 数据保留天数 | `30` |
| `CORS_ALLOW_ORIGINS` | CORS 白名单（逗号分隔） | `http://localhost:5174,http://127.0.0.1:5174` |
| `LOG_LEVEL` | 日志等级 | `INFO` |

生产环境必须替换 `ADMIN_TOKEN` 与 `INGEST_TOKEN`，禁止使用默认值。

### 前端 `frontend/.env`

| 变量 | 说明 | 示例 |
|---|---|---|
| `VITE_API_BASE` | API 基地址，默认建议相对路径 | `/api/v1` |
| `VITE_WS_BASE` | WS 基地址，留空则自动按 `window.location` 推导 | *(留空)* |
| `VITE_AUTH_TOKEN` | 前端管理令牌（对应 `ADMIN_TOKEN`） | `change-me-admin-token` |
| `VITE_ALLOWED_HOSTS` | Vite 开发允许主机（逗号分隔） | `localhost,127.0.0.1` |
| `VITE_API_PROXY_TARGET` | Vite 本地代理目标 | `http://backend:8000` |
| `VITE_BAIDU_AK` | 百度地图 AK | `<your-ak>` |
| `VITE_DEFAULT_LONGITUDE` | 默认经度 | `116.3650` |
| `VITE_DEFAULT_LATITUDE` | 默认纬度 | `40.0095` |

## 运行与联调

### 1) 手工接口验证

```bash
curl -X POST "http://${API_HOST}:8100/api/v1/runs/start" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{}"
```

### 2) 标准模拟上报脚本

```bash
python test_ingest.py \
  --host ${API_HOST} \
  --port 8100 \
  --admin-token ${ADMIN_TOKEN} \
  --ingest-token ${INGEST_TOKEN} \
  --hz 10 \
  --duration 120
```

支持参数：

- `--scheme http|https`
- `--api-prefix /api/v1`
- `--timeout`
- `--insecure`（仅测试环境）
- `--no-auto-stop`

## 前端操作说明

### 监控页 `/`

1. 点击“开始播种”创建或接入 active run。
2. 实时区会持续刷新通道值、里程、速度、告警和地图轨迹。
3. 顶部状态栏显示任务名、任务 ID、WS 连接状态与最后心跳时间。
4. 点击“停止播种”结束当前任务。
5. 点击“历史数据”进入历史页。

### 历史页 `/history`

1. 左侧列表展示最近 30 天任务，可按名称搜索和排序。
2. 选中任务后，右侧地图绘制轨迹点。
3. 操作区支持：
   - 报告：打开报告弹窗
   - 导出：导出 Excel
   - 删除：删除任务及关联数据
4. 报告弹窗支持导出 PDF/Excel。

## API 文档

完整接口文档见 [API_DOCUMENTATION.md](./API_DOCUMENTATION.md)。

## 健康检查

- `GET /healthz`：进程健康
- `GET /readyz`：数据库就绪检查

## 目录说明

```text
rsr/
├─ backend/
│  ├─ app/
│  │  ├─ api/routes.py                # REST API（runs/query/report/ingest）
│  │  ├─ core/config.py               # 环境变量解析
│  │  ├─ core/security.py             # Bearer 鉴权依赖
│  │  ├─ db/models.py                 # ORM 模型定义
│  │  ├─ db/session.py                # AsyncSession 工厂
│  │  ├─ db/bootstrap.py              # 兜底建表/补字段
│  │  ├─ services/ingest_queue.py     # 入队、批写、广播
│  │  ├─ templates/report.html        # PDF 模板
│  │  └─ main.py                      # FastAPI 入口 + 后台任务
│  ├─ migrations/versions/            # Alembic 迁移链
│  ├─ entrypoint.sh                   # 启动入口（迁移 -> 兜底 -> 启动）
│  ├─ requirements.txt
│  └─ Dockerfile
├─ frontend/
│  ├─ src/
│  │  ├─ api/http.ts                  # axios 实例 + Token 注入
│  │  ├─ api/ws.ts                    # WS 地址解析 + 自动重连
│  │  ├─ stores/runStore.ts           # run_id/ws/channel buffer 状态
│  │  ├─ components/MonitorView.vue   # 实时监控页
│  │  ├─ views/HistoryView.vue        # 历史页
│  │  └─ components/ReportModal.vue   # 报告弹窗
│  ├─ vite.config.ts                  # 开发代理与 allowedHosts
│  └─ Dockerfile
├─ scripts/
│  └─ check_no_hardcoded_domains.ps1  # 域名硬编码扫描
├─ archive/
│  └─ legacy-bak/                     # 备份文件隔离区（不参与构建）
├─ test_ingest.py                     # 标准联调脚本
├─ API_DOCUMENTATION.md               # API 开发文档
├─ prompt.txt                         # 项目提示词/约束说明
└─ docker-compose.yml
```

## 仓库治理约束

- 生产域名只允许出现在配置文件（`.env*`）。
- 备份目录（如 `bak3.2`）保留但隔离，不参与构建与发布。
- 通过 `scripts/check_no_hardcoded_domains.ps1` + CI 工作流防止域名硬编码回归。

## 迁移与数据库重置

当你从旧版本迁移并出现 Alembic 版本链冲突时，建议在维护窗口执行：

```bash
docker compose down -v
docker compose up -d --build
```

说明：

- 该操作会清空数据库卷，请先备份。
- 首次启动会自动执行迁移，失败时会执行 bootstrap 兜底。

## 常见问题

### 1. 前端报 401/403

- 检查 `frontend/.env` 中 `VITE_AUTH_TOKEN` 是否与后端 `ADMIN_TOKEN` 一致。
- 检查请求是否命中 `/api/v1` 与 `/ws/live`。

### 2. `/ingest` 返回 409

当前没有 active run。先调用 `/runs/start`。

### 3. WebSocket 一直连接中

- 检查 `/ws/live?run_id=...&token=...` 中 token 是否正确。
- 检查浏览器控制台和后端日志是否存在 `1008` 鉴权关闭。

### 4. PDF 导出失败

- 查看 `docker compose logs -f backend`。
- 确认后端容器已安装 PDF 依赖（Dockerfile 已包含 Cairo/Pango/字体）。
