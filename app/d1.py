"""
Cloudflare D1 data-access module.

All SQL for the users table lives here. Route handlers and user_store
call these functions; raw HTTP and SQL never appear elsewhere.

D1 REST API endpoint:
  POST https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{db_id}/query
  Authorization: Bearer {api_token}
  Body: {"sql": "...", "params": [...]}
"""
import logging
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_D1_TIMEOUT = 10.0  # seconds


def _url() -> str:
    acct = settings.CLOUDFLARE_ACCOUNT_ID
    db = settings.CLOUDFLARE_D1_DATABASE_ID
    if not acct or not db:
        raise RuntimeError(
            "CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_D1_DATABASE_ID must be set."
        )
    return (
        f"https://api.cloudflare.com/client/v4/accounts/{acct}"
        f"/d1/database/{db}/query"
    )


def _headers() -> dict:
    token = settings.CLOUDFLARE_API_TOKEN
    if not token:
        raise RuntimeError("CLOUDFLARE_API_TOKEN must be set.")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _query(sql: str, params: list[Any] | None = None) -> list[dict]:
    """
    Execute one SQL statement against D1 and return the result rows.

    Raises RuntimeError on any network, HTTP, or D1-level failure.
    Never returns stale data on error.
    """
    payload: dict[str, Any] = {"sql": sql}
    if params:
        payload["params"] = params

    try:
        resp = httpx.post(
            _url(),
            headers=_headers(),
            json=payload,
            timeout=_D1_TIMEOUT,
        )
    except httpx.TimeoutException as exc:
        logger.error("D1 request timed out: %s", exc)
        raise RuntimeError("D1 request timed out. Please try again.") from exc
    except httpx.RequestError as exc:
        logger.error("D1 connection error: %s", exc)
        raise RuntimeError("Could not reach Cloudflare D1. Please try again.") from exc

    if resp.status_code == 429:
        logger.error("D1 rate limit exceeded.")
        raise RuntimeError("D1 rate limit exceeded. Please try again later.")

    if resp.status_code not in (200, 201):
        logger.error("D1 HTTP %s: %s", resp.status_code, resp.text[:200])
        raise RuntimeError(f"D1 returned HTTP {resp.status_code}.")

    try:
        body = resp.json()
    except Exception as exc:
        logger.error("D1 malformed JSON response: %s", exc)
        raise RuntimeError("D1 returned a malformed response.") from exc

    if not body.get("success"):
        errors = body.get("errors", [])
        logger.error("D1 query failed: %s", errors)
        raise RuntimeError(f"D1 query failed: {errors}")

    results = body.get("result", [])
    if not results:
        return []
    # D1 returns a list of result sets; we always send one statement.
    return results[0].get("results", [])


# ---------------------------------------------------------------------------
# Public user-table operations
# ---------------------------------------------------------------------------

def db_get_user(username: str) -> Optional[dict]:
    rows = _query(
        "SELECT id, username, password_hash, is_admin, is_active, consumer_number "
        "FROM users WHERE username = ?1 LIMIT 1",
        [username],
    )
    return rows[0] if rows else None


def db_get_all_users() -> list[dict]:
    return _query(
        "SELECT id, username, password_hash, is_admin, is_active, consumer_number "
        "FROM users ORDER BY id"
    )


def db_create_user(
    username: str, password_hash: str, is_admin: bool = False
) -> None:
    existing = db_get_user(username)
    if existing:
        raise ValueError(f"Username '{username}' already exists.")
    _query(
        "INSERT INTO users (username, password_hash, is_admin, is_active) "
        "VALUES (?1, ?2, ?3, 1)",
        [username, password_hash, 1 if is_admin else 0],
    )


def db_update_user(
    old_username: str,
    new_username: Optional[str],
    new_password_hash: Optional[str],
) -> None:
    if new_username and new_username != old_username:
        conflict = db_get_user(new_username)
        if conflict:
            raise ValueError(f"Username '{new_username}' already exists.")

    if new_username and new_password_hash:
        _query(
            "UPDATE users SET username = ?1, password_hash = ?2 WHERE username = ?3",
            [new_username, new_password_hash, old_username],
        )
    elif new_username:
        _query(
            "UPDATE users SET username = ?1 WHERE username = ?2",
            [new_username, old_username],
        )
    elif new_password_hash:
        _query(
            "UPDATE users SET password_hash = ?1 WHERE username = ?2",
            [new_password_hash, old_username],
        )
    else:
        raise ValueError("Nothing to update.")

    # Verify the row was actually found and changed.
    target = new_username or old_username
    if not db_get_user(target):
        raise ValueError(f"User '{old_username}' not found.")


def db_delete_user(username: str) -> None:
    existing = db_get_user(username)
    if not existing:
        raise ValueError(f"User '{username}' not found.")
    _query("DELETE FROM users WHERE username = ?1", [username])


def db_update_consumer_number(username: str, consumer_number: str) -> None:
    existing = db_get_user(username)
    if not existing:
        raise ValueError(f"User '{username}' not found.")
    _query(
        "UPDATE users SET consumer_number = ?1 WHERE username = ?2",
        [consumer_number, username],
    )


def db_upsert_user(
    username: str,
    password_hash: str,
    is_admin: bool,
    is_active: bool,
    consumer_number: Optional[str] = None,
) -> str:
    """
    Insert or update a user by username.
    Used by the migration script only.
    Returns 'inserted' or 'updated'.
    """
    existing = db_get_user(username)
    if existing:
        _query(
            "UPDATE users SET password_hash = ?1, is_admin = ?2, is_active = ?3, "
            "consumer_number = ?4 WHERE username = ?5",
            [
                password_hash,
                1 if is_admin else 0,
                1 if is_active else 0,
                consumer_number,
                username,
            ],
        )
        return "updated"
    _query(
        "INSERT INTO users (username, password_hash, is_admin, is_active, consumer_number) "
        "VALUES (?1, ?2, ?3, ?4, ?5)",
        [
            username,
            password_hash,
            1 if is_admin else 0,
            1 if is_active else 0,
            consumer_number,
        ],
    )
    return "inserted"
