from __future__ import annotations

import secrets
from typing import Optional

from fastapi import Cookie, Header, HTTPException, WebSocket

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


def _matches_secret(candidate: Optional[str], expected: str) -> bool:
    return bool(candidate) and secrets.compare_digest(candidate, expected)


def require_admin_auth(
    authorization: Optional[str] = Header(default=None),
    admin_session: Optional[str] = Cookie(default=None, alias=settings.admin_session_cookie_name),
) -> None:
    if authorization and _matches_secret(_extract_bearer_token(authorization), settings.admin_token):
        return
    if _matches_secret(admin_session, settings.admin_token):
        return
    raise HTTPException(status_code=401, detail="Admin authentication required")


def require_ingest_token(authorization: Optional[str] = Header(default=None)) -> None:
    token = _extract_bearer_token(authorization)
    if not _matches_secret(token, settings.ingest_token):
        raise HTTPException(status_code=403, detail="Invalid ingest token")


async def websocket_require_admin_session(websocket: WebSocket) -> None:
    auth_header = websocket.headers.get("authorization")
    cookie_token = websocket.cookies.get(settings.admin_session_cookie_name)
    if auth_header:
        try:
            if _matches_secret(_extract_bearer_token(auth_header), settings.admin_token):
                return
        except HTTPException:
            pass
    if _matches_secret(cookie_token, settings.admin_token):
        return
    await websocket.close(code=4401)
