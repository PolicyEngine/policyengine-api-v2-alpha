"""Pytest fixtures for tests."""

import pytest
from sqlmodel import Session

from policyengine_api.services.database import engine


@pytest.fixture
def session():
    """Provide a database session for tests."""
    with Session(engine) as session:
        yield session
