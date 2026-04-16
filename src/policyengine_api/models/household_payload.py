"""Shared household payload models."""

from typing import Any

from sqlmodel import Field, SQLModel

from policyengine_api.config.constants import CountryId


class HouseholdEntityCollections(SQLModel):
    """Plural household entity collections used by stored and calculation APIs."""

    benunit: list[dict[str, Any]] = Field(default_factory=list)
    marital_unit: list[dict[str, Any]] = Field(default_factory=list)
    family: list[dict[str, Any]] = Field(default_factory=list)
    spm_unit: list[dict[str, Any]] = Field(default_factory=list)
    tax_unit: list[dict[str, Any]] = Field(default_factory=list)
    household: list[dict[str, Any]] = Field(default_factory=list)


class StoredHouseholdPayload(HouseholdEntityCollections):
    """Core payload shared by stored household create/read flows."""

    country_id: CountryId
    people: list[dict[str, Any]]
    year: int
    label: str | None = None
