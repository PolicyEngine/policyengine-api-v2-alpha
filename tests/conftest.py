"""Pytest fixtures for tests."""

from unittest.mock import MagicMock, patch

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
    engine.dispose()


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


@pytest.fixture(name="tax_benefit_model")
def tax_benefit_model_fixture(session: Session):
    """Create a TaxBenefitModel for tests."""
    model = TaxBenefitModel(name="policyengine-us", description="US model")
    session.add(model)
    session.commit()
    session.refresh(model)
    return model


@pytest.fixture(name="uk_tax_benefit_model")
def uk_tax_benefit_model_fixture(session: Session):
    """Create a UK TaxBenefitModel for tests."""
    model = TaxBenefitModel(name="policyengine-uk", description="UK model")
    session.add(model)
    session.commit()
    session.refresh(model)
    return model


@pytest.fixture(name="simulation_id")
def simulation_fixture(session: Session):
    """Create a test simulation with required dependencies."""
    # Create model
    model = TaxBenefitModel(name="policyengine-uk", description="UK model")
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


@pytest.fixture(name="mock_modal")
def mock_modal_fixture():
    """Mock the version resolver so Modal functions are never called in tests.

    All route files use resolve_modal_function() from version_resolver.py,
    so patching that single function intercepts all Modal calls.

    Usage:
        def test_something(mock_modal, client, simulation_id):
            response = client.post("/outputs/aggregates", json=[...])
            mock_modal.spawn.assert_called_once()
    """
    mock_fn = MagicMock()

    p = patch(
        "policyengine_api.version_resolver.resolve_modal_function",
        return_value=mock_fn,
    )
    p.start()

    yield mock_fn

    p.stop()
