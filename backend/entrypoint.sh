#!/bin/sh
set -e

echo "[INFO] Running alembic migrations..."
if ! alembic upgrade head; then
  echo "[WARN] Alembic upgrade head failed"

  echo "[INFO] Trying alembic upgrade heads (multi-head compatibility)..."
  if ! alembic upgrade heads; then
    echo "[WARN] Alembic upgrade heads failed, trying bootstrap fallback..."
    python -m app.db.bootstrap || true

    echo "[INFO] Retrying alembic upgrade heads after bootstrap..."
    if ! alembic upgrade heads; then
      echo "[WARN] Alembic still failed, stamping heads to unblock startup"
      alembic stamp heads --purge || alembic stamp 0001 --purge || true
    fi
  fi
fi

echo "[INFO] Starting backend service"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
