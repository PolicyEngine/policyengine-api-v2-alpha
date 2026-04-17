"""Regression tests for household entity list caps (#268)."""

import pytest
from pydantic import ValidationError

from policyengine_api.api.household import (
    HouseholdCalculateRequest,
    HouseholdImpactRequest,
)
from policyengine_api.models.household_payload import (
    MAX_ENTITIES_PER_GROUP,
    MAX_KEYS_PER_ENTITY,
    StoredHouseholdPayload,
)


class TestStoredHouseholdPayload:
    def test_accepts_bounded_input(self):
        payload = StoredHouseholdPayload(
            country_id="us", people=[{"age": 40}], year=2024
        )
        assert payload.year == 2024

    def test_rejects_too_many_people(self):
        too_many = [{}] * (MAX_ENTITIES_PER_GROUP + 1)
        with pytest.raises(ValidationError):
            StoredHouseholdPayload(country_id="us", people=too_many, year=2024)

    @pytest.mark.parametrize(
        "group",
        ["benunit", "marital_unit", "family", "spm_unit", "tax_unit", "household"],
    )
    def test_rejects_too_many_entities_per_group(self, group):
        too_many = [{}] * (MAX_ENTITIES_PER_GROUP + 1)
        with pytest.raises(ValidationError):
            StoredHouseholdPayload(
                country_id="us",
                people=[{}],
                year=2024,
                **{group: too_many},
            )

    def test_rejects_too_many_keys_per_entity(self):
        overfull = {f"k{i}": i for i in range(MAX_KEYS_PER_ENTITY + 1)}
        with pytest.raises(ValidationError):
            StoredHouseholdPayload(
                country_id="us",
                people=[overfull],
                year=2024,
            )


class TestHouseholdCalculateRequest:
    def test_rejects_too_many_people(self):
        with pytest.raises(ValidationError):
            HouseholdCalculateRequest(
                people=[{}] * (MAX_ENTITIES_PER_GROUP + 1),
                country_id="us",
            )

    def test_rejects_too_many_tax_units(self):
        with pytest.raises(ValidationError):
            HouseholdCalculateRequest(
                people=[{}],
                tax_unit=[{}] * (MAX_ENTITIES_PER_GROUP + 1),
                country_id="us",
            )

    def test_rejects_too_many_keys_per_entity(self):
        overfull = {f"k{i}": i for i in range(MAX_KEYS_PER_ENTITY + 1)}
        with pytest.raises(ValidationError):
            HouseholdCalculateRequest(
                people=[overfull],
                country_id="us",
            )


class TestHouseholdImpactRequest:
    def test_rejects_too_many_people(self):
        with pytest.raises(ValidationError):
            HouseholdImpactRequest(
                people=[{}] * (MAX_ENTITIES_PER_GROUP + 1),
                country_id="us",
            )
