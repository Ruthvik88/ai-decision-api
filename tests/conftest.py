"""
Pytest configuration and shared fixtures for AI Decision API tests.

Uses an in-memory SQLite database with StaticPool to keep test state isolated
from the persistent application database (decisions.db).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api import app
from src.database import Base, get_db

# ---------------------------------------------------------------------------
# Test database setup (in-memory SQLite, isolated from production decisions.db)
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite://"

engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Dependency override providing sessions bound to the test database."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    """
    Create fresh database tables before each test and drop them after,
    ensuring a clean slate and no cross-test pollution.
    """
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


# Shared TestClient instance for tests
client = TestClient(app)


@pytest.fixture
def test_client():
    """Fixture yielding a TestClient for tests requiring a fixture."""
    with TestClient(app) as c:
        yield c
