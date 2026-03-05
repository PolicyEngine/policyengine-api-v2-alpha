"""Integration tests for database models and relationships.

These tests require a running Supabase instance and seeded database.
Run with: make integration-test
"""

import pytest

pytestmark = pytest.mark.integration

from datetime import datetime, timezone

from rich.console import Console
from sqlmodel import Session, create_engine, select

from policyengine_api.config.settings import settings
from policyengine_api.models import (
    Dataset,
    DatasetVersion,
    Dynamic,
    Parameter,
    ParameterValue,
    Policy,
    Simulation,
    SimulationStatus,
    TaxBenefitModel,
    TaxBenefitModelVersion,
    Variable,
)

console = Console()


@pytest.fixture(scope="session")
def engine():
    """Create database engine for testing."""
    return create_engine(settings.database_url, echo=False)


@pytest.fixture(scope="function")
def session(engine):
    """Create database session for each test."""
    with Session(engine) as session:
        yield session


def test_database_connection(session):
    """Test that we can connect to the database."""
    console.print("[blue]Testing database connection...")
    assert session is not None
    console.print("[green]✓ Database connection successful")


def test_tax_benefit_models_seeded(session):
    """Test that tax-benefit models are properly seeded."""
    console.print("[blue]Testing tax-benefit models...")

    models = session.exec(select(TaxBenefitModel)).all()
    assert len(models) >= 2, "Expected at least UK and US models"

    model_names = {m.name for m in models}
    assert "uk" in model_names or "policyengine-uk" in model_names
    assert "us" in model_names or "policyengine-us" in model_names

    console.print(f"[green]✓ Found {len(models)} tax-benefit models")


def test_model_versions_seeded(session):
    """Test that model versions are properly seeded."""
    console.print("[blue]Testing model versions...")

    versions = session.exec(select(TaxBenefitModelVersion)).all()
    assert len(versions) >= 2, "Expected at least UK and US versions"

    # Test relationships
    for version in versions:
        assert version.model is not None, "Version should have a model"
        assert version.model.id is not None
        assert version.version is not None

    console.print(f"[green]✓ Found {len(versions)} model versions")


def test_variables_seeded(session):
    """Test that variables are properly seeded."""
    console.print("[blue]Testing variables...")

    variables = session.exec(select(Variable)).all()
    assert len(variables) > 0, "Expected variables to be seeded"

    # Test that each variable has proper relationships
    for var in variables[:5]:  # Check first 5
        assert var.tax_benefit_model_version is not None
        assert var.name is not None
        assert var.entity is not None

    console.print(f"[green]✓ Found {len(variables)} variables")


def test_parameters_seeded(session):
    """Test that parameters are properly seeded."""
    console.print("[blue]Testing parameters...")

    parameters = session.exec(select(Parameter)).all()
    assert len(parameters) > 0, "Expected parameters to be seeded"

    # Test relationships
    for param in parameters[:5]:  # Check first 5
        assert param.tax_benefit_model_version is not None
        assert param.name is not None

    console.print(f"[green]✓ Found {len(parameters)} parameters")


def test_parameter_values_seeded(session):
    """Test that parameter values are properly seeded."""
    console.print("[blue]Testing parameter values...")

    param_values = session.exec(select(ParameterValue)).all()
    assert len(param_values) > 0, "Expected parameter values to be seeded"

    # Test relationships
    for pv in param_values[:5]:  # Check first 5
        assert pv.parameter is not None
        assert pv.value_json is not None
        assert pv.start_date is not None

    console.print(f"[green]✓ Found {len(param_values)} parameter values")


def test_datasets_seeded(session):
    """Test that datasets are properly seeded."""
    console.print("[blue]Testing datasets...")

    datasets = session.exec(select(Dataset)).all()
    assert len(datasets) > 0, "Expected datasets to be seeded"

    # Test that datasets have proper fields
    for dataset in datasets:
        assert dataset.name is not None
        assert dataset.filepath is not None
        assert dataset.year is not None
        assert dataset.tax_benefit_model_id is not None

    console.print(f"[green]✓ Found {len(datasets)} datasets")


def test_policy_creation_with_parameter_values(session):
    """Test creating a policy with parameter values."""
    console.print("[blue]Testing policy creation with parameter values...")

    # Get a parameter to create a value for
    parameter = session.exec(select(Parameter).limit(1)).first()
    assert parameter is not None, "Need at least one parameter"

    # Create policy
    policy = Policy(
        name="Test Policy",
        description="Integration test policy",
    )
    session.add(policy)
    session.commit()
    session.refresh(policy)

    # Create parameter value linked to policy
    param_value = ParameterValue(
        parameter_id=parameter.id,
        value_json={"value": 15000},
        start_date=datetime.now(timezone.utc),
        policy_id=policy.id,
    )
    session.add(param_value)
    session.commit()

    # Verify relationship
    session.refresh(policy)
    assert len(policy.parameter_values) == 1
    assert policy.parameter_values[0].parameter_id == parameter.id

    # Cleanup
    session.delete(param_value)
    session.delete(policy)
    session.commit()

    console.print("[green]✓ Policy creation with parameter values works")


def test_dynamic_creation_with_parameter_values(session):
    """Test creating a dynamic with parameter values."""
    console.print("[blue]Testing dynamic creation with parameter values...")

    # Get a parameter
    parameter = session.exec(select(Parameter).limit(1)).first()
    assert parameter is not None

    # Create dynamic
    dynamic = Dynamic(
        name="Test Dynamic",
        description="Integration test dynamic",
    )
    session.add(dynamic)
    session.commit()
    session.refresh(dynamic)

    # Create parameter value linked to dynamic
    param_value = ParameterValue(
        parameter_id=parameter.id,
        value_json={"value": 0.03},
        start_date=datetime.now(timezone.utc),
        dynamic_id=dynamic.id,
    )
    session.add(param_value)
    session.commit()

    # Verify relationship
    session.refresh(dynamic)
    assert len(dynamic.parameter_values) == 1
    assert dynamic.parameter_values[0].parameter_id == parameter.id

    # Cleanup
    session.delete(param_value)
    session.delete(dynamic)
    session.commit()

    console.print("[green]✓ Dynamic creation with parameter values works")


def test_simulation_creation_with_relationships(session):
    """Test creating a simulation with all relationships."""
    console.print("[blue]Testing simulation creation with relationships...")

    # Get required models
    dataset = session.exec(select(Dataset).limit(1)).first()
    assert dataset is not None, "Need at least one dataset"

    model_version = session.exec(select(TaxBenefitModelVersion).limit(1)).first()
    assert model_version is not None, "Need at least one model version"

    # Create policy
    policy = Policy(name="Test Sim Policy", description="For simulation test")
    session.add(policy)
    session.commit()
    session.refresh(policy)

    # Create simulation
    simulation = Simulation(
        dataset_id=dataset.id,
        policy_id=policy.id,
        tax_benefit_model_version_id=model_version.id,
        status=SimulationStatus.PENDING,
    )
    session.add(simulation)
    session.commit()
    session.refresh(simulation)

    # Verify relationships
    assert simulation.dataset is not None
    assert simulation.dataset.id == dataset.id
    assert simulation.policy is not None
    assert simulation.policy.id == policy.id
    assert simulation.tax_benefit_model_version is not None
    assert simulation.tax_benefit_model_version.id == model_version.id

    # Cleanup
    session.delete(simulation)
    session.delete(policy)
    session.commit()

    console.print("[green]✓ Simulation creation with relationships works")


def test_dataset_version_creation(session):
    """Test creating a dataset version."""
    console.print("[blue]Testing dataset version creation...")

    # Get required models
    dataset = session.exec(select(Dataset).limit(1)).first()
    assert dataset is not None

    model = session.exec(select(TaxBenefitModel).limit(1)).first()
    assert model is not None

    # Create dataset version
    version = DatasetVersion(
        name="v1.0",
        description="Test version",
        dataset_id=dataset.id,
        tax_benefit_model_id=model.id,
    )
    session.add(version)
    session.commit()
    session.refresh(version)

    # Verify relationships
    assert version.dataset is not None
    assert version.dataset.id == dataset.id
    assert version.tax_benefit_model is not None
    assert version.tax_benefit_model.id == model.id

    # Verify reverse relationship
    session.refresh(dataset)
    assert any(v.id == version.id for v in dataset.versions)

    # Cleanup
    session.delete(version)
    session.commit()

    console.print("[green]✓ Dataset version creation works")


def test_model_relationship_integrity(session):
    """Test that all model relationships are properly configured."""
    console.print("[blue]Testing model relationship integrity...")

    # Get a model version and verify all relationships work
    version = session.exec(select(TaxBenefitModelVersion).limit(1)).first()
    assert version is not None

    # Test model relationship
    assert version.model is not None
    assert version.model.id is not None

    # Test variables relationship
    assert isinstance(version.variables, list)

    # Test parameters relationship
    assert isinstance(version.parameters, list)

    # Verify reverse relationships work
    if len(version.variables) > 0:
        var = version.variables[0]
        assert var.tax_benefit_model_version.id == version.id

    if len(version.parameters) > 0:
        param = version.parameters[0]
        assert param.tax_benefit_model_version.id == version.id

    console.print("[green]✓ Model relationship integrity verified")


def test_parameter_value_belongs_to_policy_or_dynamic(session):
    """Test parameter values belong to either policy or dynamic (not both)."""
    console.print("[blue]Testing parameter value ownership...")

    # Get all parameter values
    param_values = session.exec(select(ParameterValue)).all()

    for pv in param_values:
        # A parameter value should belong to at most one of: Policy, Dynamic, or neither
        belongs_to_policy = pv.policy_id is not None
        belongs_to_dynamic = pv.dynamic_id is not None

        # Shouldn't belong to both
        assert not (belongs_to_policy and belongs_to_dynamic), (
            "Parameter value should not belong to both Policy and Dynamic"
        )

    console.print("[green]✓ Parameter value ownership is correct")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
