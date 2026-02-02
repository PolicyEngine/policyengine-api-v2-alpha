"""Fixtures and helpers for user-household association tests."""

from uuid import UUID

from policyengine_api.models import Household, User, UserHouseholdAssociation

# -----------------------------------------------------------------------------
# Factory functions
# -----------------------------------------------------------------------------


def create_user(
    session,
    first_name: str = "Test",
    last_name: str = "User",
    email: str = "test@example.com",
) -> User:
    """Create and persist a User record."""
    record = User(first_name=first_name, last_name=last_name, email=email)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def create_household(
    session,
    tax_benefit_model_name: str = "policyengine_us",
    year: int = 2024,
    label: str | None = "Test household",
) -> Household:
    """Create and persist a Household record."""
    record = Household(
        tax_benefit_model_name=tax_benefit_model_name,
        year=year,
        label=label,
        household_data={"people": [{"age": 30}]},
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def create_association(
    session,
    user_id: UUID,
    household_id: UUID,
    country_id: str = "us",
    label: str | None = "My household",
) -> UserHouseholdAssociation:
    """Create and persist a UserHouseholdAssociation record."""
    record = UserHouseholdAssociation(
        user_id=user_id,
        household_id=household_id,
        country_id=country_id,
        label=label,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record
