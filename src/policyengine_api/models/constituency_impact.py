"""UK parliamentary constituency impact output model."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class ConstituencyImpactBase(SQLModel):
    """Base constituency impact fields."""

    baseline_simulation_id: UUID = Field(foreign_key="simulations.id")
    reform_simulation_id: UUID = Field(foreign_key="simulations.id")
    report_id: UUID | None = Field(default=None, foreign_key="reports.id")
    constituency_code: str
    constituency_name: str
    x: int
    y: int
    average_household_income_change: float
    relative_household_income_change: float
    population: float


class ConstituencyImpact(ConstituencyImpactBase, table=True):
    """Constituency impact database model."""

    __tablename__ = "constituency_impacts"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConstituencyImpactCreate(ConstituencyImpactBase):
    """Schema for creating constituency impacts."""

    pass


class ConstituencyImpactRead(ConstituencyImpactBase):
    """Schema for reading constituency impacts."""

    id: UUID
    created_at: datetime
