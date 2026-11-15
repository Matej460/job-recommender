"""Shared setup for the API tests.

The tests must not touch the real PostgreSQL data, so every test gets its own
empty in-memory SQLite database. FastAPI's dependency override replaces get_db,
so the endpoints use that test database instead of PostgreSQL.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",                                  # in-memory database
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,                         # one shared connection keeps the data alive
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
