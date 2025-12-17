"""Decile impact output model."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class DecileImpactBase(SQLModel):
    """Base decile impact fields."""

    baseline_simulation_id: UUID = Field(foreign_key="simulations.id")
    reform_simulation_id: UUID = Field(foreign_key="simulations.id")
    report_id: UUID | None = Field(default=None, foreign_key="reports.id")
    income_variable: str
    entity: str | None = None
    decile: int
    quantiles: int = 10
    baseline_mean: float | None = None
    reform_mean: float | None = None
    absolute_change: float | None = None
    relative_change: float | None = None
    count_better_off: float | None = None
    count_worse_off: float | None = None
    count_no_change: float | None = None


class DecileImpact(DecileImpactBase, table=True):
    """Decile impact database model."""

    __tablename__ = "decile_impacts"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DecileImpactCreate(DecileImpactBase):
    """Schema for creating decile impacts."""

    pass


class DecileImpactRead(DecileImpactBase):
    """Schema for reading decile impacts."""

    id: UUID
    created_at: datetime
