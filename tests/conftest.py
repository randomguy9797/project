import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
from app.models import User
from app.auth import hash_password

SQLALCHEMY_TEST_URL = "sqlite:///./test.db"

engine = create_engine(SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


@pytest.fixture
def db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def test_user(db):
    user = User(username="testuser", password_hash=hash_password("testpass123"))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_csrf(client: TestClient, path: str = "/login") -> tuple[str, dict]:
    """Return (csrf_token, cookies) from a GET request."""
    resp = client.get(path)
    csrf = resp.cookies.get("csrf_token", "")
    return csrf, dict(resp.cookies)
