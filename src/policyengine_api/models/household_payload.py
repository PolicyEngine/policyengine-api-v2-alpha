"""Shared household payload models."""

from typing import Annotated, Any

from pydantic import AfterValidator
from sqlmodel import Field, SQLModel

from policyengine_api.config.constants import CountryId

# Upper bound on how many entities a household payload may contain. The
# simulation kernel is not designed for arbitrarily wide inputs, and an
# unbounded list lets a single request pin the entire process on memory.
MAX_ENTITIES_PER_GROUP = 1000

# Upper bound on distinct keys per entity dict (e.g. variables per person).
# Each key becomes a column in a MicroDataFrame; unbounded keys would let
# a request blow up memory during dataset construction.
MAX_KEYS_PER_ENTITY = 500


def _cap_keys_per_entity(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reject entity lists where any dict exceeds MAX_KEYS_PER_ENTITY keys."""
    for idx, entity in enumerate(values):
        if isinstance(entity, dict) and len(entity) > MAX_KEYS_PER_ENTITY:
            raise ValueError(
                f"Entity at index {idx} has {len(entity)} keys; "
                f"maximum is {MAX_KEYS_PER_ENTITY}"
            )
    return values


_BoundedEntityList = Annotated[
    list[dict[str, Any]],
    AfterValidator(_cap_keys_per_entity),
]


class HouseholdEntityCollections(SQLModel):
    """Plural household entity collections used by stored and calculation APIs."""

    benunit: _BoundedEntityList = Field(
        default_factory=list, max_length=MAX_ENTITIES_PER_GROUP
    )
    marital_unit: _BoundedEntityList = Field(
        default_factory=list, max_length=MAX_ENTITIES_PER_GROUP
    )
    family: _BoundedEntityList = Field(
        default_factory=list, max_length=MAX_ENTITIES_PER_GROUP
    )
    spm_unit: _BoundedEntityList = Field(
        default_factory=list, max_length=MAX_ENTITIES_PER_GROUP
    )
    tax_unit: _BoundedEntityList = Field(
        default_factory=list, max_length=MAX_ENTITIES_PER_GROUP
    )
    household: _BoundedEntityList = Field(
        default_factory=list, max_length=MAX_ENTITIES_PER_GROUP
    )


class StoredHouseholdPayload(HouseholdEntityCollections):
    """Core payload shared by stored household create/read flows."""

    country_id: CountryId
    people: _BoundedEntityList = Field(max_length=MAX_ENTITIES_PER_GROUP)
    year: int
    label: str | None = None
