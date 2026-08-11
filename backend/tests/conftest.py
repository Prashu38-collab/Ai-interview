"""Pytest fixtures: in-memory SQLite DB, TestClient, and helpers.

Env vars must be set before any app module is imported (config is cached),
so this file sets them at the top before importing from ``app``.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef0123456789abcdef")
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("CORS_ORIGINS", "http://testserver")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.database import Base, get_db
from app.main import app


@pytest.fixture()
def db_session():
    """Create a fresh in-memory database for each test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session):
    """TestClient wired to the in-memory database via dependency override."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client):
    """Register + login a user and return Authorization headers."""
    payload = {
        "email": "candidate@example.com",
        "full_name": "Test Candidate",
        "password": "supersecret123",
    }
    client.post("/auth/register", json=payload)
    res = client.post("/auth/login", json=payload)
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
