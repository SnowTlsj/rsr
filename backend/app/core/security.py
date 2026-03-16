from __future__ import annotations

import secrets
from typing import Optional

from fastapi import Header, HTTPException

from app.core.config import settings


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return token


def require_admin_token(authorization: Optional[str] = Header(default=None)) -> None:
    token = _extract_bearer_token(authorization)
    if not secrets.compare_digest(token, settings.admin_token):
        raise HTTPException(status_code=403, detail="Invalid admin token")


def require_ingest_token(authorization: Optional[str] = Header(default=None)) -> None:
    token = _extract_bearer_token(authorization)
    if not secrets.compare_digest(token, settings.ingest_token):
        raise HTTPException(status_code=403, detail="Invalid ingest token")
