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

MOCK_US_MULTI_GROUP_HOUSEHOLD_CREATE = {
    "country_id": "us",
    "year": 2024,
    "label": "US multi-group household",
    "people": [
        {
            "person_id": 0,
            "person_household_id": 0,
            "person_tax_unit_id": 0,
            "person_marital_unit_id": 0,
            "age": 30,
            "employment_income": 50000,
        },
        {
            "person_id": 1,
            "person_household_id": 0,
            "person_tax_unit_id": 0,
            "person_marital_unit_id": 1,
            "age": 28,
            "employment_income": 30000,
        },
    ],
    "tax_unit": [{"tax_unit_id": 0, "state_name": "CA"}],
    "marital_unit": [
        {"marital_unit_id": 0},
        {"marital_unit_id": 1},
    ],
    "family": [{"family_id": 0}],
    "spm_unit": [{"spm_unit_id": 0}],
    "household": [{"household_id": 0, "state_name": "CA"}],
}

MOCK_US_FULL_MULTI_GROUP_HOUSEHOLD_CREATE = {
    "country_id": "us",
    "year": 2024,
    "label": "US fully multi-group household",
    "people": [
        {
            "person_id": 0,
            "person_household_id": 0,
            "person_tax_unit_id": 0,
            "person_marital_unit_id": 0,
            "person_family_id": 0,
            "person_spm_unit_id": 0,
            "age": 30,
            "employment_income": 50000,
        },
        {
            "person_id": 1,
            "person_household_id": 1,
            "person_tax_unit_id": 1,
            "person_marital_unit_id": 1,
            "person_family_id": 1,
            "person_spm_unit_id": 1,
            "age": 28,
            "employment_income": 30000,
        },
    ],
    "tax_unit": [
        {"tax_unit_id": 0, "state_name": "CA"},
        {"tax_unit_id": 1, "state_name": "CA"},
    ],
    "marital_unit": [
        {"marital_unit_id": 0},
        {"marital_unit_id": 1},
    ],
    "family": [
        {"family_id": 0},
        {"family_id": 1},
    ],
    "spm_unit": [
        {"spm_unit_id": 0},
        {"spm_unit_id": 1},
    ],
    "household": [
        {"household_id": 0, "state_name": "CA"},
        {"household_id": 1, "state_name": "NY"},
    ],
}

MOCK_HOUSEHOLD_MINIMAL = {
    "country_id": "us",
    "year": 2024,
    "people": [{"age": 25}],
}

MOCK_US_HOUSEHOLD_CREATE_LEGACY = {
    "country_id": "us",
    "year": 2024,
    "label": "US legacy household",
    "people": [
        {"age": 30, "employment_income": 50000},
        {"age": 28, "employment_income": 30000},
    ],
    "tax_unit": {},
    "family": {},
    "household": {"state_name": "CA"},
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
