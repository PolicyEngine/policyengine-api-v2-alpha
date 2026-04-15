"""Fixtures and helpers for household CRUD tests."""

from policyengine_api.models import Household

# -----------------------------------------------------------------------------
# Request payloads (match HouseholdCreate schema)
# -----------------------------------------------------------------------------

MOCK_US_HOUSEHOLD_CREATE = {
    "country_id": "us",
    "year": 2024,
    "label": "US test household",
    "people": [
        {"age": 30, "employment_income": 50000},
        {"age": 28, "employment_income": 30000},
    ],
    "tax_unit": [{}],
    "family": [{}],
    "household": [{"state_name": "CA"}],
}

MOCK_UK_HOUSEHOLD_CREATE = {
    "country_id": "uk",
    "year": 2024,
    "label": "UK test household",
    "people": [
        {"age": 40, "employment_income": 35000},
    ],
    "benunit": [{"is_married": False}],
    "household": [{"region": "LONDON"}],
}

MOCK_HOUSEHOLD_MINIMAL = {
    "country_id": "us",
    "year": 2024,
    "people": [{"age": 25}],
}


# -----------------------------------------------------------------------------
# Factory functions
# -----------------------------------------------------------------------------


def create_household(
    session,
    country_id: str = "us",
    year: int = 2024,
    label: str | None = "Test household",
    people: list | None = None,
    **entity_groups,
) -> Household:
    """Create and persist a Household record."""
    household_data = {"people": people or [{"age": 30}]}
    household_data.update(entity_groups)

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
