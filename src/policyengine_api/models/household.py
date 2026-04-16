"""Stored household definition model."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import field_validator, model_validator
from sqlalchemy import JSON
from sqlmodel import Column, Field, SQLModel

from policyengine_api.models.household_payload import StoredHouseholdPayload

_ENTITY_ID_KEY_BY_GROUP = {
    "benunit": "benunit_id",
    "marital_unit": "marital_unit_id",
    "family": "family_id",
    "spm_unit": "spm_unit_id",
    "tax_unit": "tax_unit_id",
    "household": "household_id",
}

_ENTITY_GROUP_FIELDS = tuple(_ENTITY_ID_KEY_BY_GROUP.keys())


def _coerce_entity_group_collection(value: Any) -> Any:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return value


class HouseholdBase(SQLModel):
    """Base household fields."""

    country_id: str
    year: int
    label: str | None = None
    household_data: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))


class Household(HouseholdBase, table=True):
    """Stored household database model."""

    __tablename__ = "households"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HouseholdCreate(StoredHouseholdPayload):
    """Schema for creating a stored household.

    Uses the same list-based relational entity shape as the household
    calculation APIs.
    """

    @field_validator(*_ENTITY_GROUP_FIELDS, mode="before")
    @classmethod
    def coerce_legacy_singular_entity_groups(cls, value: Any) -> Any:
        return _coerce_entity_group_collection(value)

    @model_validator(mode="after")
    def validate_relationships(self) -> "HouseholdCreate":
        person_ids = [
            person["person_id"]
            for person in self.people
            if person.get("person_id") is not None
        ]
        if len(person_ids) != len(set(person_ids)):
            raise ValueError("people contains duplicate person_id values")

        for group_key, entity_id_key in _ENTITY_ID_KEY_BY_GROUP.items():
            entity_records = getattr(self, group_key)
            person_link_key = f"person_{entity_id_key}"

            entity_ids = [
                entity[entity_id_key]
                for entity in entity_records
                if entity.get(entity_id_key) is not None
            ]

            if len(entity_ids) != len(set(entity_ids)):
                raise ValueError(
                    f"{group_key} contains duplicate {entity_id_key} values"
                )

            requires_linkage = len(entity_records) > 1
            person_links = []
            for person in self.people:
                person_link = person.get(person_link_key)
                if person_link is None:
                    if requires_linkage:
                        raise ValueError(
                            f"people must include {person_link_key} when {group_key} has multiple rows"
                        )
                    continue
                person_links.append(person_link)

            if not person_links:
                continue

            if len(entity_ids) != len(entity_records):
                raise ValueError(
                    f"{group_key} rows must all include {entity_id_key} when people reference {person_link_key}"
                )

            unknown_links = sorted(set(person_links) - set(entity_ids))
            if unknown_links:
                raise ValueError(
                    f"{group_key} is missing rows for referenced {entity_id_key} values: {unknown_links}"
                )

        return self


class HouseholdRead(HouseholdCreate):
    """Schema for reading a stored household."""

    id: UUID
    created_at: datetime
    updated_at: datetime
