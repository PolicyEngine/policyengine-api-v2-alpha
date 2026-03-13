"""Test database models."""

from uuid import uuid4

from policyengine_api.models import (
    AggregateOutput,
    AggregateType,
    Dataset,
    Household,
    Policy,
    Simulation,
    SimulationStatus,
    Variable,
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


def test_variable_creation_with_default_value():
    """Test variable model creation with default_value field."""
    model_version_id = uuid4()
    variable = Variable(
        name="age",
        entity="person",
        description="Age of the person",
        data_type="int",
        default_value=40,
        tax_benefit_model_version_id=model_version_id,
    )
    assert variable.name == "age"
    assert variable.entity == "person"
    assert variable.data_type == "int"
    assert variable.default_value == 40
    assert variable.id is not None


def test_variable_with_float_default_value():
    """Test variable model with float default value."""
    model_version_id = uuid4()
    variable = Variable(
        name="employment_income",
        entity="person",
        data_type="float",
        default_value=0.0,
        tax_benefit_model_version_id=model_version_id,
    )
    assert variable.default_value == 0.0


def test_variable_with_bool_default_value():
    """Test variable model with boolean default value."""
    model_version_id = uuid4()
    variable = Variable(
        name="is_disabled",
        entity="person",
        data_type="bool",
        default_value=False,
        tax_benefit_model_version_id=model_version_id,
    )
    assert variable.default_value is False


def test_variable_with_string_default_value():
    """Test variable model with string default value (enum)."""
    model_version_id = uuid4()
    variable = Variable(
        name="state_name",
        entity="household",
        data_type="Enum",
        default_value="CA",
        possible_values=["CA", "NY", "TX"],
        tax_benefit_model_version_id=model_version_id,
    )
    assert variable.default_value == "CA"
    assert variable.possible_values == ["CA", "NY", "TX"]


def test_variable_with_null_default_value():
    """Test variable model with null default value."""
    model_version_id = uuid4()
    variable = Variable(
        name="optional_field",
        entity="person",
        data_type="str",
        default_value=None,
        tax_benefit_model_version_id=model_version_id,
    )
    assert variable.default_value is None


def test_variable_with_adds():
    """Test variable model with adds field."""
    model_version_id = uuid4()
    adds_components = ["employment_income", "self_employment_income", "pension_income"]
    variable = Variable(
        name="total_income",
        entity="person",
        data_type="float",
        default_value=0.0,
        adds=adds_components,
        tax_benefit_model_version_id=model_version_id,
    )
    assert variable.adds == adds_components
    assert variable.subtracts is None


def test_variable_with_subtracts():
    """Test variable model with subtracts field."""
    model_version_id = uuid4()
    subtracts_components = ["tax_deduction", "personal_allowance"]
    variable = Variable(
        name="adjusted_income",
        entity="person",
        data_type="float",
        default_value=0.0,
        subtracts=subtracts_components,
        tax_benefit_model_version_id=model_version_id,
    )
    assert variable.subtracts == subtracts_components
    assert variable.adds is None


def test_variable_with_adds_and_subtracts():
    """Test variable model with both adds and subtracts fields."""
    model_version_id = uuid4()
    adds_components = ["gross_income", "capital_gains"]
    subtracts_components = ["standard_deduction"]
    variable = Variable(
        name="taxable_income",
        entity="person",
        data_type="float",
        default_value=0.0,
        adds=adds_components,
        subtracts=subtracts_components,
        tax_benefit_model_version_id=model_version_id,
    )
    assert variable.adds == adds_components
    assert variable.subtracts == subtracts_components


def test_variable_with_null_adds_and_subtracts():
    """Test variable model defaults adds/subtracts to None."""
    model_version_id = uuid4()
    variable = Variable(
        name="age",
        entity="person",
        data_type="int",
        default_value=40,
        tax_benefit_model_version_id=model_version_id,
    )
    assert variable.adds is None
    assert variable.subtracts is None


def test_variable_with_empty_adds():
    """Test variable model with empty adds list."""
    model_version_id = uuid4()
    variable = Variable(
        name="placeholder_variable",
        entity="person",
        data_type="float",
        default_value=0.0,
        adds=[],
        tax_benefit_model_version_id=model_version_id,
    )
    assert variable.adds == []
    assert variable.subtracts is None


def test_household_creation():
    """Test household model creation."""
    household = Household(
        country_id="us",
        year=2024,
        label="Test household",
        household_data={"people": [{"age": 30}], "household": {}},
    )
    assert household.household_data == {"people": [{"age": 30}], "household": {}}
    assert household.label == "Test household"
    assert household.country_id == "us"
    assert household.year == 2024
    assert household.id is not None
