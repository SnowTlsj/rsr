#!/bin/sh
set -e

echo "[INFO] Running alembic migrations..."
if ! alembic upgrade head; then
  echo "[WARN] Alembic upgrade head failed, trying bootstrap fallback..."
  python -m app.db.bootstrap
  alembic upgrade head
fi

echo "[INFO] Starting backend service"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
