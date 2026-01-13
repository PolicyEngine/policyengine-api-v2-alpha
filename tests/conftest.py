"""Pytest fixtures for tests."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from policyengine_api.main import app
from policyengine_api.models import (
    Dataset,
    Simulation,
    SimulationStatus,
    TaxBenefitModel,
    TaxBenefitModelVersion,
)
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


@pytest.fixture(name="simulation_id")
def simulation_fixture(session: Session):
    """Create a test simulation with required dependencies."""
    # Create model
    model = TaxBenefitModel(name="policyengine_uk", description="UK model")
    session.add(model)
    session.commit()
    session.refresh(model)

    # Create model version
    version = TaxBenefitModelVersion(
        model_id=model.id,
        version="test",
        description="Test version",
    )
    session.add(version)
    session.commit()
    session.refresh(version)

    # Create dataset
    dataset = Dataset(
        name="test_dataset",
        description="Test dataset",
        filepath="test/path/dataset.h5",
        year=2024,
        tax_benefit_model_id=model.id,
    )
    session.add(dataset)
    session.commit()
    session.refresh(dataset)

    # Create simulation
    simulation = Simulation(
        dataset_id=dataset.id,
        tax_benefit_model_version_id=version.id,
        status=SimulationStatus.COMPLETED,
    )
    session.add(simulation)
    session.commit()
    session.refresh(simulation)

    return str(simulation.id)
