"""Fixtures and helpers for parameter-related tests."""

from datetime import datetime, timezone

import pytest

from policyengine_api.models import (
    Parameter,
    ParameterValue,
    Policy,
    TaxBenefitModel,
    TaxBenefitModelVersion,
)

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def model_version(session):
    """Create a TaxBenefitModel and TaxBenefitModelVersion for testing."""
    model = TaxBenefitModel(name="test-model", description="Test model")
    session.add(model)
    session.commit()
    session.refresh(model)

    version = TaxBenefitModelVersion(
        model_id=model.id,
        version="1.0.0",
        description="Test version",
    )
    session.add(version)
    session.commit()
    session.refresh(version)
    return version


# -----------------------------------------------------------------------------
# Factory Functions
# -----------------------------------------------------------------------------


def create_parameter(session, model_version, name: str, label: str) -> Parameter:
    """Create and persist a Parameter."""
    param = Parameter(
        name=name,
        label=label,
        tax_benefit_model_version_id=model_version.id,
    )
    session.add(param)
    session.commit()
    session.refresh(param)
    return param


def create_policy(session, name: str, description: str = "A test policy") -> Policy:
    """Create and persist a Policy."""
    policy = Policy(name=name, description=description)
    session.add(policy)
    session.commit()
    session.refresh(policy)
    return policy


def create_parameter_value(
    session,
    parameter_id,
    value: int | float | dict,
    policy_id=None,
    start_date: datetime | None = None,
) -> ParameterValue:
    """Create and persist a ParameterValue."""
    pv = ParameterValue(
        parameter_id=parameter_id,
        value_json=value,
        start_date=start_date or datetime.now(timezone.utc),
        policy_id=policy_id,
    )
    session.add(pv)
    session.commit()
    session.refresh(pv)
    return pv


def create_parameter_values_batch(
    session,
    parameter_id,
    count: int,
    value_multiplier: int = 100,
) -> list[ParameterValue]:
    """Create multiple ParameterValues for a parameter."""
    pvs = []
    for i in range(count):
        pv = ParameterValue(
            parameter_id=parameter_id,
            value_json=i * value_multiplier,
            start_date=datetime.now(timezone.utc),
        )
        session.add(pv)
        pvs.append(pv)
    session.commit()
    for pv in pvs:
        session.refresh(pv)
    return pvs
