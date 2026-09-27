import secrets
import time
from typing import Optional
from fastapi import Request, Response
from app.config import settings

# In-memory session store: {session_id: {"username": str, "expires_at": float}}
_sessions: dict[str, dict] = {}

COOKIE_NAME = "session_id"


def create_session(response: Response, username: str) -> str:
    session_id = secrets.token_urlsafe(32)
    expires_at = time.time() + settings.SESSION_MAX_AGE
    _sessions[session_id] = {"username": username, "expires_at": expires_at}
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_id,
        max_age=settings.SESSION_MAX_AGE,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
    )
    return session_id


def get_session(request: Request) -> Optional[dict]:
    session_id = request.cookies.get(COOKIE_NAME)
    if not session_id:
        return None
    session = _sessions.get(session_id)
    if not session:
        return None
    if time.time() > session["expires_at"]:
        _sessions.pop(session_id, None)
        return None
    return session


def delete_session(request: Request, response: Response) -> None:
    session_id = request.cookies.get(COOKIE_NAME)
    if session_id:
        _sessions.pop(session_id, None)
    response.delete_cookie(key=COOKIE_NAME, httponly=True, samesite="lax")


def get_current_username(request: Request) -> Optional[str]:
    session = get_session(request)
    if session:
        return session.get("username")
    return None
