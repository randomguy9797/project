import time
import pytest
from fastapi.testclient import TestClient
from tests.conftest import get_csrf
from app import sessions as session_store


def login(client, username, password):
    csrf, cookies = get_csrf(client)
    return client.post(
        "/login",
        data={"username": username, "password": password, "csrf_token": csrf},
        cookies=cookies,
    )


def test_valid_login(client, test_user):
    resp = login(client, "testuser", "testpass123")
    assert resp.status_code == 302
    assert resp.headers["location"] == "/form"


def test_invalid_password(client, test_user):
    resp = login(client, "testuser", "wrongpassword")
    assert resp.status_code == 401
    assert "Invalid username or password" in resp.text


def test_invalid_username(client, test_user):
    resp = login(client, "nobody", "testpass123")
    assert resp.status_code == 401
    assert "Invalid username or password" in resp.text


def test_unauthenticated_form_redirect(client):
    resp = client.get("/form")
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


def test_logout(client, test_user):
    resp = login(client, "testuser", "testpass123")
    session_cookie = resp.cookies.get("session_id")
    csrf, cookies = get_csrf(client, "/form")
    cookies["session_id"] = session_cookie
    logout_resp = client.post("/logout", data={"csrf_token": csrf}, cookies=cookies)
    assert logout_resp.status_code == 302

    # After logout, /form should redirect to login
    form_resp = client.get("/form", cookies={"session_id": session_cookie})
    assert form_resp.status_code == 302


def test_session_expiry(client, test_user, monkeypatch):
    resp = login(client, "testuser", "testpass123")
    session_id = resp.cookies.get("session_id")
    # Manually expire the session
    if session_id in session_store._sessions:
        session_store._sessions[session_id]["expires_at"] = time.time() - 1

    form_resp = client.get("/form", cookies={"session_id": session_id})
    assert form_resp.status_code == 302


def test_csrf_missing_on_login(client, test_user):
    resp = client.post(
        "/login",
        data={"username": "testuser", "password": "testpass123", "csrf_token": "bad"},
    )
    assert resp.status_code == 400
