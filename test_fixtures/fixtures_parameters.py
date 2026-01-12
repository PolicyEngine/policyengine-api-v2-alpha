"""Fixtures and helpers for parameter-related tests."""

from datetime import datetime, timedelta, timezone

import pytest

from policyengine_api.models import (
    Parameter,
    ParameterValue,
    Policy,
    TaxBenefitModel,
    TaxBenefitModelVersion,
    Variable,
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


def create_model_and_version(
    session,
    model_name: str = "test-model",
    version_string: str = "1.0.0",
    created_at_offset_days: int = 0,
) -> tuple[TaxBenefitModel, TaxBenefitModelVersion]:
    """Create a TaxBenefitModel and TaxBenefitModelVersion.

    Args:
        session: Database session.
        model_name: Name for the model.
        version_string: Version string (e.g., "1.0.0").
        created_at_offset_days: Days to offset created_at (negative for past).

    Returns:
        Tuple of (model, version).
    """
    # Check if model already exists
    from sqlmodel import select

    existing_model = session.exec(
        select(TaxBenefitModel).where(TaxBenefitModel.name == model_name)
    ).first()

    if existing_model:
        model = existing_model
    else:
        model = TaxBenefitModel(name=model_name, description=f"Test model {model_name}")
        session.add(model)
        session.commit()
        session.refresh(model)

    created_at = datetime.now(timezone.utc) + timedelta(days=created_at_offset_days)
    version = TaxBenefitModelVersion(
        model_id=model.id,
        version=version_string,
        description=f"Version {version_string}",
        created_at=created_at,
    )
    session.add(version)
    session.commit()
    session.refresh(version)
    return model, version


def create_variable(
    session, model_version, name: str, entity: str = "person"
) -> Variable:
    """Create and persist a Variable."""
    var = Variable(
        name=name,
        entity=entity,
        description=f"Test variable {name}",
        data_type="float",
        tax_benefit_model_version_id=model_version.id,
    )
    session.add(var)
    session.commit()
    session.refresh(var)
    return var


# -----------------------------------------------------------------------------
# Multi-Version Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def two_model_versions(session):
    """Create a model with two versions (old and new) for testing version filtering.

    Returns a dict with:
        - model: The TaxBenefitModel
        - old_version: The older TaxBenefitModelVersion (created 10 days ago)
        - new_version: The newer TaxBenefitModelVersion (created now)
    """
    model, old_version = create_model_and_version(
        session,
        model_name="policyengine-us",
        version_string="1.0.0",
        created_at_offset_days=-10,
    )
    _, new_version = create_model_and_version(
        session,
        model_name="policyengine-us",
        version_string="2.0.0",
        created_at_offset_days=0,
    )
    return {
        "model": model,
        "old_version": old_version,
        "new_version": new_version,
    }
