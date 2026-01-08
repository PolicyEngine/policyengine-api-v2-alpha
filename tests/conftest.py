"""Pytest fixtures for tests."""

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

# Load environment variables from .env file
load_dotenv()
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from policyengine_api.main import app
from policyengine_api.services.database import get_session


@pytest.fixture(name="session")
def session_fixture():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Create a test client with the test session."""
    # Initialize the cache for tests
    FastAPICache.init(InMemoryBackend(), prefix="test-cache")

    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
