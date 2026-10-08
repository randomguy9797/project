import hmac
import hashlib
import secrets
import time
from fastapi import Request, Response
from app.config import settings

CSRF_COOKIE = "csrf_token"
TOKEN_TTL = 3600  # 1 hour


def _sign(token: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(), token.encode(), hashlib.sha256
    ).hexdigest()


def generate_csrf_token(response: Response) -> str:
    raw = f"{secrets.token_urlsafe(32)}.{int(time.time())}"
    signed = f"{raw}.{_sign(raw)}"
    response.set_cookie(
        key=CSRF_COOKIE,
        value=signed,
        httponly=False,  # must be readable by the form (it's in a hidden field)
        secure=settings.is_production,
        samesite="lax",
        max_age=TOKEN_TTL,
    )
    return signed


def validate_csrf(request: Request, form_token: str) -> bool:
    cookie_token = request.cookies.get(CSRF_COOKIE, "")
    if not cookie_token or not form_token:
        return False
    if not hmac.compare_digest(cookie_token, form_token):
        return False
    try:
        parts = cookie_token.rsplit(".", 2)
        if len(parts) != 3:
            return False
        raw = f"{parts[0]}.{parts[1]}"
        expected_sig = _sign(raw)
        if not hmac.compare_digest(expected_sig, parts[2]):
            return False
        issued_at = int(parts[1])
        if time.time() - issued_at > TOKEN_TTL:
            return False
    except (ValueError, IndexError):
        return False
    return True
