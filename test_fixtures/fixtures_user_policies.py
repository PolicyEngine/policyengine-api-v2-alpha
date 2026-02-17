"""Fixtures and helpers for user-policy association tests."""

from uuid import UUID

from policyengine_api.models import Policy, TaxBenefitModel, UserPolicy

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

US_COUNTRY_ID = "us"
UK_COUNTRY_ID = "uk"

DEFAULT_POLICY_NAME = "Test policy"
DEFAULT_POLICY_DESCRIPTION = "A test policy"

# -----------------------------------------------------------------------------
# Factory functions
# -----------------------------------------------------------------------------


def create_tax_benefit_model(
    session,
    name: str = "policyengine-us",
    description: str = "US model",
) -> TaxBenefitModel:
    """Create and persist a TaxBenefitModel record."""
    record = TaxBenefitModel(name=name, description=description)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def create_policy(
    session,
    tax_benefit_model: TaxBenefitModel,
    name: str = DEFAULT_POLICY_NAME,
    description: str = DEFAULT_POLICY_DESCRIPTION,
) -> Policy:
    """Create and persist a Policy record."""
    record = Policy(
        name=name,
        description=description,
        tax_benefit_model_id=tax_benefit_model.id,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def create_user_policy(
    session,
    user_id: UUID,
    policy: Policy,
    country_id: str = US_COUNTRY_ID,
    label: str | None = None,
) -> UserPolicy:
    """Create and persist a UserPolicy association record."""
    record = UserPolicy(
        user_id=user_id,
        policy_id=policy.id,
        country_id=country_id,
        label=label,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record
