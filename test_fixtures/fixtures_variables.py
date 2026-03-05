"""Fixtures and helpers for variable-related tests."""

import pytest

from policyengine_api.models import (
    TaxBenefitModel,
    TaxBenefitModelVersion,
    Variable,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def us_model_version(session):
    """Create a policyengine-us model and version for testing."""
    model = TaxBenefitModel(name="policyengine-us", description="US model")
    session.add(model)
    session.commit()
    session.refresh(model)

    version = TaxBenefitModelVersion(
        model_id=model.id,
        version="1.0.0",
        description="Test US version",
    )
    session.add(version)
    session.commit()
    session.refresh(version)
    return version


@pytest.fixture
def uk_model_version(session):
    """Create a policyengine-uk model and version for testing."""
    model = TaxBenefitModel(name="policyengine-uk", description="UK model")
    session.add(model)
    session.commit()
    session.refresh(model)

    version = TaxBenefitModelVersion(
        model_id=model.id,
        version="1.0.0",
        description="Test UK version",
    )
    session.add(version)
    session.commit()
    session.refresh(version)
    return version


# ---------------------------------------------------------------------------
# Factory Functions
# ---------------------------------------------------------------------------


def create_variable(
    session,
    model_version,
    name: str,
    label: str | None = None,
    entity: str = "person",
    description: str | None = None,
    data_type: str | None = "float",
) -> Variable:
    """Create and persist a Variable."""
    var = Variable(
        name=name,
        label=label,
        entity=entity,
        description=description,
        data_type=data_type,
        tax_benefit_model_version_id=model_version.id,
    )
    session.add(var)
    session.commit()
    session.refresh(var)
    return var
