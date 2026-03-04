"""Fixtures and helpers for version-filtering tests.

Provides reusable model/version/parameter/variable factories and composite
fixtures for testing version-filter behaviour across endpoints.
"""

from datetime import datetime, timezone

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
# Constants
# -----------------------------------------------------------------------------

MODEL_NAMES = {
    "US": "policyengine-us",
    "UK": "policyengine-uk",
}

VERSION_TIMESTAMPS = {
    "V1": datetime(2025, 1, 1, tzinfo=timezone.utc),
    "V2": datetime(2025, 6, 1, tzinfo=timezone.utc),
}


# -----------------------------------------------------------------------------
# Factory Functions
# -----------------------------------------------------------------------------


def create_model(
    session, name: str = MODEL_NAMES["US"], description: str = "Test model"
) -> TaxBenefitModel:
    """Create and persist a TaxBenefitModel."""
    model = TaxBenefitModel(name=name, description=description)
    session.add(model)
    session.commit()
    session.refresh(model)
    return model


def create_version(
    session,
    model: TaxBenefitModel,
    version: str = "1.0.0",
    created_at: datetime | None = None,
) -> TaxBenefitModelVersion:
    """Create and persist a TaxBenefitModelVersion."""
    ver = TaxBenefitModelVersion(
        model_id=model.id,
        version=version,
        description=f"Version {version}",
        **({"created_at": created_at} if created_at else {}),
    )
    session.add(ver)
    session.commit()
    session.refresh(ver)
    return ver


def create_parameter(
    session,
    model_version: TaxBenefitModelVersion,
    name: str,
    label: str = "",
    description: str | None = None,
) -> Parameter:
    """Create and persist a Parameter."""
    param = Parameter(
        name=name,
        label=label or name.rsplit(".", 1)[-1],
        description=description,
        tax_benefit_model_version_id=model_version.id,
    )
    session.add(param)
    session.commit()
    session.refresh(param)
    return param


def create_variable(
    session,
    model_version: TaxBenefitModelVersion,
    name: str,
    entity: str = "person",
    description: str | None = None,
) -> Variable:
    """Create and persist a Variable."""
    var = Variable(
        name=name,
        entity=entity,
        description=description,
        tax_benefit_model_version_id=model_version.id,
    )
    session.add(var)
    session.commit()
    session.refresh(var)
    return var


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


def create_policy(
    session,
    model: TaxBenefitModel,
    name: str = "Test Policy",
) -> Policy:
    """Create and persist a Policy."""
    policy = Policy(
        name=name,
        description=f"Policy: {name}",
        tax_benefit_model_id=model.id,
    )
    session.add(policy)
    session.commit()
    session.refresh(policy)
    return policy


def add_params_bulk(session, version, names_and_labels):
    """Bulk-add parameters.  names_and_labels is [(name, label), ...]."""
    for name, label in names_and_labels:
        session.add(
            Parameter(
                name=name,
                label=label,
                tax_benefit_model_version_id=version.id,
            )
        )
    session.commit()


# -----------------------------------------------------------------------------
# Composite Fixtures — single model + single version
# -----------------------------------------------------------------------------


@pytest.fixture
def us_model(session):
    """Create a policyengine-us model."""
    return create_model(session, MODEL_NAMES["US"], "US model")


@pytest.fixture
def uk_model(session):
    """Create a policyengine-uk model."""
    return create_model(session, MODEL_NAMES["UK"], "UK model")


@pytest.fixture
def us_version(session, us_model):
    """Create a single US model version."""
    return create_version(session, us_model, "1.0")


@pytest.fixture
def uk_version(session, uk_model):
    """Create a single UK model version."""
    return create_version(session, uk_model, "1.0")


# -----------------------------------------------------------------------------
# Composite Fixtures — single model + TWO versions (for version-filter tests)
# -----------------------------------------------------------------------------


@pytest.fixture
def us_two_versions(session, us_model):
    """Create two US versions: v1 (old) and v2 (latest)."""
    v1 = create_version(session, us_model, "1.0", VERSION_TIMESTAMPS["V1"])
    v2 = create_version(session, us_model, "2.0", VERSION_TIMESTAMPS["V2"])
    return v1, v2


@pytest.fixture
def uk_two_versions(session, uk_model):
    """Create two UK versions: v1 (old) and v2 (latest)."""
    v1 = create_version(session, uk_model, "1.0", VERSION_TIMESTAMPS["V1"])
    v2 = create_version(session, uk_model, "2.0", VERSION_TIMESTAMPS["V2"])
    return v1, v2
