"""Stored household definition model."""

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import JSON
from sqlmodel import Column, Field, SQLModel


class HouseholdBase(SQLModel):
    """Base household fields."""

    tax_benefit_model_name: str
    year: int
    label: str | None = None
    household_data: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))


class Household(HouseholdBase, table=True):
    """Stored household database model."""

    __tablename__ = "households"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HouseholdCreate(SQLModel):
    """Schema for creating a stored household.

    Accepts the flat structure matching the frontend Household interface:
    people as an array, entity groups as optional dicts.
    """

    tax_benefit_model_name: Literal["policyengine_us", "policyengine_uk"]
    year: int
    label: str | None = None
    people: list[dict[str, Any]]
    tax_unit: dict[str, Any] | None = None
    family: dict[str, Any] | None = None
    spm_unit: dict[str, Any] | None = None
    marital_unit: dict[str, Any] | None = None
    household: dict[str, Any] | None = None
    benunit: dict[str, Any] | None = None


class HouseholdRead(HouseholdCreate):
    """Schema for reading a stored household."""

    id: UUID
    created_at: datetime
    updated_at: datetime
