"""Fixtures and helpers for household analysis endpoint tests."""

from typing import Any
from unittest.mock import patch
from uuid import UUID

import pytest
from sqlmodel import Session

from policyengine_api.models import (
    Household,
    Parameter,
    ParameterValue,
    Policy,
    TaxBenefitModel,
    TaxBenefitModelVersion,
)

# =============================================================================
# Sample Calculation Results
# =============================================================================


SAMPLE_UK_BASELINE_RESULT: dict[str, Any] = {
    "person": [
        {
            "age": 30,
            "employment_income": 35000.0,
            "income_tax": 4500.0,
            "national_insurance": 2800.0,
            "net_income": 27700.0,
        }
    ],
    "benunit": [
        {
            "universal_credit": 0.0,
            "child_benefit": 0.0,
        }
    ],
    "household": [
        {
            "region": "LONDON",
            "council_tax": 1500.0,
        }
    ],
}


SAMPLE_UK_REFORM_RESULT: dict[str, Any] = {
    "person": [
        {
            "age": 30,
            "employment_income": 35000.0,
            "income_tax": 4000.0,
            "national_insurance": 2800.0,
            "net_income": 28200.0,
        }
    ],
    "benunit": [
        {
            "universal_credit": 0.0,
            "child_benefit": 0.0,
        }
    ],
    "household": [
        {
            "region": "LONDON",
            "council_tax": 1500.0,
        }
    ],
}


SAMPLE_US_BASELINE_RESULT: dict[str, Any] = {
    "person": [
        {
            "age": 30,
            "employment_income": 50000.0,
            "income_tax": 6000.0,
            "fica": 3825.0,
            "net_income": 40175.0,
        }
    ],
    "tax_unit": [
        {
            "state_code": "CA",
            "state_income_tax": 2500.0,
        }
    ],
    "spm_unit": [{"snap": 0.0}],
    "family": [{}],
    "marital_unit": [{}],
    "household": [{"state_fips": 6}],
}


SAMPLE_US_REFORM_RESULT: dict[str, Any] = {
    "person": [
        {
            "age": 30,
            "employment_income": 50000.0,
            "income_tax": 5500.0,
            "fica": 3825.0,
            "net_income": 40675.0,
        }
    ],
    "tax_unit": [
        {
            "state_code": "CA",
            "state_income_tax": 2500.0,
        }
    ],
    "spm_unit": [{"snap": 0.0}],
    "family": [{}],
    "marital_unit": [{}],
    "household": [{"state_fips": 6}],
}


# =============================================================================
# Mock Calculator Functions
# =============================================================================


def mock_calculate_uk_household(
    household_data: dict[str, Any],
    year: int,
    policy_data: dict | None,
) -> dict:
    """Mock UK calculator that returns sample results."""
    if policy_data:
        return SAMPLE_UK_REFORM_RESULT
    return SAMPLE_UK_BASELINE_RESULT


def mock_calculate_us_household(
    household_data: dict[str, Any],
    year: int,
    policy_data: dict | None,
) -> dict:
    """Mock US calculator that returns sample results."""
    if policy_data:
        return SAMPLE_US_REFORM_RESULT
    return SAMPLE_US_BASELINE_RESULT


def mock_calculate_household_failing(
    household_data: dict[str, Any],
    year: int,
    policy_data: dict | None,
) -> dict:
    """Mock calculator that raises an exception."""
    raise RuntimeError("Calculation failed")


# =============================================================================
# Pytest Fixtures for Mocking
# =============================================================================


@pytest.fixture
def mock_uk_calculator():
    """Fixture that patches UK calculator with mock."""
    with patch(
        "policyengine_api.api.household_analysis.calculate_uk_household",
        side_effect=mock_calculate_uk_household,
    ) as mock:
        yield mock


@pytest.fixture
def mock_us_calculator():
    """Fixture that patches US calculator with mock."""
    with patch(
        "policyengine_api.api.household_analysis.calculate_us_household",
        side_effect=mock_calculate_us_household,
    ) as mock:
        yield mock


@pytest.fixture
def mock_calculators():
    """Fixture that patches both UK and US calculators."""
    with (
        patch(
            "policyengine_api.api.household_analysis.calculate_uk_household",
            side_effect=mock_calculate_uk_household,
        ) as uk_mock,
        patch(
            "policyengine_api.api.household_analysis.calculate_us_household",
            side_effect=mock_calculate_us_household,
        ) as us_mock,
    ):
        yield {"uk": uk_mock, "us": us_mock}


@pytest.fixture
def mock_failing_calculator():
    """Fixture that patches calculators to fail."""
    with (
        patch(
            "policyengine_api.api.household_analysis.calculate_uk_household",
            side_effect=mock_calculate_household_failing,
        ),
        patch(
            "policyengine_api.api.household_analysis.calculate_us_household",
            side_effect=mock_calculate_household_failing,
        ),
    ):
        yield


# =============================================================================
# Database Factory Functions
# =============================================================================


def create_tax_benefit_model(
    session: Session,
    name: str = "policyengine-uk",
    description: str = "UK tax benefit model",
) -> TaxBenefitModel:
    """Create and persist a TaxBenefitModel record."""
    model = TaxBenefitModel(
        name=name,
        description=description,
    )
    session.add(model)
    session.commit()
    session.refresh(model)
    return model


def create_model_version(
    session: Session,
    model_id: UUID,
    version: str = "1.0.0",
    description: str = "Test version",
) -> TaxBenefitModelVersion:
    """Create and persist a TaxBenefitModelVersion record."""
    model_version = TaxBenefitModelVersion(
        model_id=model_id,
        version=version,
        description=description,
    )
    session.add(model_version)
    session.commit()
    session.refresh(model_version)
    return model_version


def create_parameter(
    session: Session,
    model_version_id: UUID,
    name: str = "test_parameter",
    label: str = "Test Parameter",
    description: str = "A test parameter",
) -> Parameter:
    """Create and persist a Parameter record."""
    param = Parameter(
        tax_benefit_model_version_id=model_version_id,
        name=name,
        label=label,
        description=description,
    )
    session.add(param)
    session.commit()
    session.refresh(param)
    return param


def create_policy(
    session: Session,
    model_id: UUID,
    name: str = "Test Policy",
    description: str = "A test policy",
) -> Policy:
    """Create and persist a Policy record."""
    policy = Policy(
        tax_benefit_model_id=model_id,
        name=name,
        description=description,
    )
    session.add(policy)
    session.commit()
    session.refresh(policy)
    return policy


def create_policy_with_parameter_value(
    session: Session,
    model_id: UUID,
    parameter_id: UUID,
    value: float,
    name: str = "Test Policy",
) -> Policy:
    """Create a Policy with an associated ParameterValue."""
    policy = create_policy(session, model_id, name=name)

    param_value = ParameterValue(
        policy_id=policy.id,
        parameter_id=parameter_id,
        value_json={"value": value},
    )
    session.add(param_value)
    session.commit()
    session.refresh(policy)
    return policy


def create_household_for_analysis(
    session: Session,
    country_id: str = "uk",
    year: int = 2024,
    label: str = "Test household for analysis",
) -> Household:
    """Create a household suitable for analysis testing."""
    if country_id == "uk":
        household_data = {
            "people": [{"age": 30, "employment_income": 35000}],
            "benunit": {},
            "household": {"region": "LONDON"},
        }
    else:
        household_data = {
            "people": [{"age": 30, "employment_income": 50000}],
            "tax_unit": {"state_code": "CA"},
            "family": {},
            "spm_unit": {},
            "marital_unit": {},
            "household": {"state_fips": 6},
        }

    record = Household(
        country_id=country_id,
        year=year,
        label=label,
        household_data=household_data,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def setup_uk_model_and_version(
    session: Session,
) -> tuple[TaxBenefitModel, TaxBenefitModelVersion]:
    """Create UK model and version for testing."""
    model = create_tax_benefit_model(
        session, name="policyengine-uk", description="UK model"
    )
    version = create_model_version(session, model.id)
    return model, version


def setup_us_model_and_version(
    session: Session,
) -> tuple[TaxBenefitModel, TaxBenefitModelVersion]:
    """Create US model and version for testing."""
    model = create_tax_benefit_model(
        session, name="policyengine-us", description="US model"
    )
    version = create_model_version(session, model.id)
    return model, version
