# Seed Monitor (Vue3 + FastAPI + PostgreSQL)

## Quick Start (Docker Compose)

1) Copy env files

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

2) Start services

```bash
docker compose up --build
```

3) Run migrations

```bash
docker compose exec backend alembic upgrade head
```

Frontend: http://localhost:5173
Backend: http://localhost:8000

## Ingest Example (with token)

```bash
curl -X POST "http://localhost:8000/api/v1/ingest" \
  -H "Authorization: Bearer devtoken" \
  -H "Content-Type: application/json" \
  -d '{
    "ts": "2025-01-01T12:00:00Z",
    "machine_id": "machine-001",
    "telemetry": {
      "seed_channels_g": [10.2, 9.8, 10.5, 9.9, 10.1],
      "seed_total_g": 50.5,
      "distance_m": 120.4,
      "leak_distance_m": 1.2,
      "speed_kmh": 4.2,
      "alarm_blocked": false,
      "alarm_no_seed": false
    },
    "gps": {
      "lon": 116.365,
      "lat": 40.0095,
      "alt_m": 50.2,
      "heading_deg": 120.0
    }
  }'
```

## MonitorView Usage

- Click **开始播种** to create a run and open the WebSocket stream.
- Click **停止播种** to close the stream and end the run.
- Click **趋势表格** to toggle the channel table with sparklines.
- Click **历史数据** to open the HistoryView.

## HistoryView Usage

- The left list shows runs from the last 30 days.
- Click a run to load GPS points and draw the red trajectory on the Baidu map.

## Notes

- The backend keeps only the last 30 days of runs (daily cleanup task).
- Data is partitioned by `run_id` only; tables are fixed: `runs`, `telemetry_samples`, `gps_points`.
- Baidu Map GL is injected via `frontend/index.html` and used through `window.BMapGL`.
