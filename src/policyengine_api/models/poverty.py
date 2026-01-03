"""Poverty output model."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class PovertyBase(SQLModel):
    """Base poverty fields."""

    simulation_id: UUID = Field(foreign_key="simulations.id")
    report_id: UUID | None = Field(default=None, foreign_key="reports.id")
    poverty_type: str  # e.g. "absolute_bhc", "spm", etc.
    entity: str = "person"
    filter_variable: str | None = None
    headcount: float | None = None
    total_population: float | None = None
    rate: float | None = None


class Poverty(PovertyBase, table=True):
    """Poverty database model."""

    __tablename__ = "poverty"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PovertyCreate(PovertyBase):
    """Schema for creating poverty records."""

    pass


class PovertyRead(PovertyBase):
    """Schema for reading poverty records."""

    id: UUID
    created_at: datetime
