"""
Tests for app.d1 and app.user_store.

Uses httpx.MockTransport to intercept D1 REST calls — no real network or
Cloudflare account required.
"""
import json
import pytest
import httpx

import app.d1 as d1_module
from app.d1 import (
    db_get_user, db_get_all_users, db_create_user,
    db_update_user, db_delete_user, db_upsert_user,
)
from app.user_store import (
    get_user, get_all_users, count_users, create_user,
    update_user, delete_user,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _d1_ok(rows: list[dict]) -> httpx.Response:
    body = {"success": True, "result": [{"results": rows}], "errors": []}
    return httpx.Response(200, json=body)


def _d1_error(message: str = "query error") -> httpx.Response:
    body = {"success": False, "result": [], "errors": [{"message": message}]}
    return httpx.Response(200, json=body)


class _SequentialTransport(httpx.MockTransport):
    """Return responses from a queue in order."""

    def __init__(self, responses: list[httpx.Response]):
        self._queue = list(responses)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        assert self._queue, "Unexpected extra D1 request"
        return self._queue.pop(0)


def _patch_client(monkeypatch, responses: list[httpx.Response]):
    transport = _SequentialTransport(responses)

    def _fake_post(url, *, headers, json, timeout):
        req = httpx.Request("POST", url, headers=headers, json=json)
        return transport.handle_request(req)

    monkeypatch.setattr(httpx, "post", _fake_post)
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "test-acct")
    monkeypatch.setenv("CLOUDFLARE_D1_DATABASE_ID", "test-db")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-token")
    # Reload settings so env vars are picked up
    from app import config
    config.settings.CLOUDFLARE_ACCOUNT_ID = "test-acct"
    config.settings.CLOUDFLARE_D1_DATABASE_ID = "test-db"
    config.settings.CLOUDFLARE_API_TOKEN = "test-token"


_ALICE = {
    "id": 1, "username": "alice", "password_hash": "$argon2id$v=19$...",
    "is_admin": 1, "is_active": 1, "consumer_number": None,
}
_BOB = {
    "id": 2, "username": "bob", "password_hash": "$argon2id$v=19$...",
    "is_admin": 0, "is_active": 1, "consumer_number": "12345",
}


# ---------------------------------------------------------------------------
# db_get_user
# ---------------------------------------------------------------------------

def test_get_user_found(monkeypatch):
    _patch_client(monkeypatch, [_d1_ok([_ALICE])])
    user = db_get_user("alice")
    assert user["username"] == "alice"
    assert user["is_admin"] == 1


def test_get_user_not_found(monkeypatch):
    _patch_client(monkeypatch, [_d1_ok([])])
    assert db_get_user("nobody") is None


def test_get_user_d1_error_raises(monkeypatch):
    _patch_client(monkeypatch, [_d1_error("syntax error")])
    with pytest.raises(RuntimeError, match="D1 query failed"):
        db_get_user("alice")


def test_get_user_timeout_raises(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "test-acct")
    monkeypatch.setenv("CLOUDFLARE_D1_DATABASE_ID", "test-db")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-token")
    from app import config
    config.settings.CLOUDFLARE_ACCOUNT_ID = "test-acct"
    config.settings.CLOUDFLARE_D1_DATABASE_ID = "test-db"
    config.settings.CLOUDFLARE_API_TOKEN = "test-token"

    def _timeout(*a, **kw):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx, "post", _timeout)
    with pytest.raises(RuntimeError, match="timed out"):
        db_get_user("alice")


def test_get_user_rate_limit_raises(monkeypatch):
    _patch_client(monkeypatch, [httpx.Response(429)])
    with pytest.raises(RuntimeError, match="rate limit"):
        db_get_user("alice")


# ---------------------------------------------------------------------------
# db_get_all_users
# ---------------------------------------------------------------------------

def test_get_all_users(monkeypatch):
    _patch_client(monkeypatch, [_d1_ok([_ALICE, _BOB])])
    users = db_get_all_users()
    assert len(users) == 2
    assert users[0]["username"] == "alice"


# ---------------------------------------------------------------------------
# db_create_user
# ---------------------------------------------------------------------------

def test_create_user_success(monkeypatch):
    # First call: check duplicate (returns empty) → second call: INSERT
    _patch_client(monkeypatch, [_d1_ok([]), _d1_ok([])])
    db_create_user("carol", "$argon2id$...", is_admin=False)  # should not raise


def test_create_user_duplicate_raises(monkeypatch):
    _patch_client(monkeypatch, [_d1_ok([_ALICE])])
    with pytest.raises(ValueError, match="already exists"):
        db_create_user("alice", "$argon2id$...")


# ---------------------------------------------------------------------------
# db_update_user
# ---------------------------------------------------------------------------

def test_update_user_password(monkeypatch):
    # check conflict (no new_username) → UPDATE → verify
    _patch_client(monkeypatch, [_d1_ok([]), _d1_ok([{**_ALICE, "password_hash": "$new$"}])])
    db_update_user("alice", None, "$new$")  # should not raise


def test_update_user_username_conflict(monkeypatch):
    _patch_client(monkeypatch, [_d1_ok([_BOB])])
    with pytest.raises(ValueError, match="already exists"):
        db_update_user("alice", "bob", None)


def test_update_user_nothing_to_update(monkeypatch):
    _patch_client(monkeypatch, [])
    with pytest.raises(ValueError, match="Nothing to update"):
        db_update_user("alice", None, None)


# ---------------------------------------------------------------------------
# db_delete_user
# ---------------------------------------------------------------------------

def test_delete_user_success(monkeypatch):
    _patch_client(monkeypatch, [_d1_ok([_BOB]), _d1_ok([])])
    db_delete_user("bob")  # should not raise


def test_delete_user_not_found(monkeypatch):
    _patch_client(monkeypatch, [_d1_ok([])])
    with pytest.raises(ValueError, match="not found"):
        db_delete_user("nobody")


# ---------------------------------------------------------------------------
# db_upsert_user (migration helper)
# ---------------------------------------------------------------------------

def test_upsert_insert(monkeypatch):
    _patch_client(monkeypatch, [_d1_ok([]), _d1_ok([])])
    result = db_upsert_user("dave", "$argon2id$...", False, True)
    assert result == "inserted"


def test_upsert_update(monkeypatch):
    _patch_client(monkeypatch, [_d1_ok([_ALICE]), _d1_ok([])])
    result = db_upsert_user("alice", "$argon2id$new$", True, True)
    assert result == "updated"


# ---------------------------------------------------------------------------
# user_store public API (thin wrappers — smoke test)
# ---------------------------------------------------------------------------

def test_user_store_get_user(monkeypatch):
    _patch_client(monkeypatch, [_d1_ok([_ALICE])])
    assert get_user("alice")["username"] == "alice"


def test_user_store_count_users(monkeypatch):
    _patch_client(monkeypatch, [_d1_ok([_ALICE, _BOB])])
    assert count_users() == 2


def test_user_store_create_user(monkeypatch):
    _patch_client(monkeypatch, [_d1_ok([]), _d1_ok([])])
    create_user("eve", "$argon2id$...")  # should not raise


def test_user_store_delete_user(monkeypatch):
    _patch_client(monkeypatch, [_d1_ok([_BOB]), _d1_ok([])])
    delete_user("bob")  # should not raise
