"""Inequality output model."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class InequalityBase(SQLModel):
    """Base inequality fields."""

    simulation_id: UUID = Field(foreign_key="simulations.id")
    report_id: UUID | None = Field(default=None, foreign_key="reports.id")
    income_variable: str
    entity: str = "household"
    gini: float | None = None
    top_10_share: float | None = None
    top_1_share: float | None = None
    bottom_50_share: float | None = None


class Inequality(InequalityBase, table=True):
    """Inequality database model."""

    __tablename__ = "inequality"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class InequalityCreate(InequalityBase):
    """Schema for creating inequality records."""

    pass


class InequalityRead(InequalityBase):
    """Schema for reading inequality records."""

    id: UUID
    created_at: datetime
