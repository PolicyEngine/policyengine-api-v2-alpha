"""Stored household definition model."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON
from sqlmodel import Column, Field, SQLModel

from policyengine_api.models.household_payload import HouseholdPayloadBase


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


class HouseholdCreate(HouseholdPayloadBase):
    """Schema for creating a stored household.

    Uses the same plural entity-list shape as the household calculation API:
    people as an array, entity groups as optional lists.
    """


class HouseholdRead(HouseholdCreate):
    """Schema for reading a stored household."""

    id: UUID
    created_at: datetime
    updated_at: datetime
