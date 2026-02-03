"""Fixtures and helpers for analysis endpoint tests."""

from uuid import UUID

from sqlmodel import Session

from policyengine_api.models import (
    Household,
    Parameter,
    ParameterValue,
    Policy,
    TaxBenefitModel,
    TaxBenefitModelVersion,
)


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
    model_version_id: UUID,
    name: str = "Test Policy",
    description: str = "A test policy",
) -> Policy:
    """Create and persist a Policy record."""
    policy = Policy(
        tax_benefit_model_version_id=model_version_id,
        name=name,
        description=description,
    )
    session.add(policy)
    session.commit()
    session.refresh(policy)
    return policy


def create_policy_with_parameter_value(
    session: Session,
    model_version_id: UUID,
    parameter_id: UUID,
    value: float,
    name: str = "Test Policy",
) -> Policy:
    """Create a Policy with an associated ParameterValue."""
    policy = create_policy(session, model_version_id, name=name)

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
    tax_benefit_model_name: str = "policyengine_uk",
    year: int = 2024,
    label: str = "Test household for analysis",
) -> Household:
    """Create a household suitable for analysis testing."""
    if tax_benefit_model_name == "policyengine_uk":
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
        tax_benefit_model_name=tax_benefit_model_name,
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
