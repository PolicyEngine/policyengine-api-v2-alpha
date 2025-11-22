"""Test database models."""

from uuid import uuid4

from policyengine_api.models import (
    AggregateOutput,
    AggregateType,
    Dataset,
    Policy,
    Simulation,
    SimulationStatus,
)


def test_dataset_creation():
    """Test dataset model creation."""
    tax_benefit_model_id = uuid4()
    dataset = Dataset(
        name="Test Dataset",
        description="Test description",
        filepath="/data/test.h5",
        year=2026,
        tax_benefit_model_id=tax_benefit_model_id,
    )
    assert dataset.name == "Test Dataset"
    assert dataset.year == 2026
    assert dataset.tax_benefit_model_id == tax_benefit_model_id
    assert dataset.id is not None


def test_policy_creation():
    """Test policy model creation."""
    policy = Policy(
        name="Test Policy",
        description="Test policy description",
    )
    assert policy.name == "Test Policy"
    assert policy.description == "Test policy description"


def test_simulation_creation():
    """Test simulation model creation."""
    dataset_id = uuid4()
    model_version_id = uuid4()
    simulation = Simulation(
        dataset_id=dataset_id,
        tax_benefit_model_version_id=model_version_id,
        status=SimulationStatus.PENDING,
    )
    assert simulation.dataset_id == dataset_id
    assert simulation.tax_benefit_model_version_id == model_version_id
    assert simulation.status == SimulationStatus.PENDING
    assert simulation.error_message is None


def test_aggregate_output_creation():
    """Test aggregate model creation."""
    simulation_id = uuid4()
    output = AggregateOutput(
        simulation_id=simulation_id,
        variable="universal_credit",
        aggregate_type=AggregateType.SUM,
        entity="benunit",
        filter_config={},
    )
    assert output.simulation_id == simulation_id
    assert output.aggregate_type == AggregateType.SUM
    assert output.result is None
