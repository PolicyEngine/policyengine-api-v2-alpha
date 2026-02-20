"""Congressional district impact output model."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class CongressionalDistrictImpactBase(SQLModel):
    """Base congressional district impact fields."""

    baseline_simulation_id: UUID = Field(foreign_key="simulations.id")
    reform_simulation_id: UUID = Field(foreign_key="simulations.id")
    report_id: UUID | None = Field(default=None, foreign_key="reports.id")
    district_geoid: int
    state_fips: int
    district_number: int
    average_household_income_change: float
    relative_household_income_change: float
    population: float


class CongressionalDistrictImpact(CongressionalDistrictImpactBase, table=True):
    """Congressional district impact database model."""

    __tablename__ = "congressional_district_impacts"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CongressionalDistrictImpactCreate(CongressionalDistrictImpactBase):
    """Schema for creating congressional district impacts."""

    pass


class CongressionalDistrictImpactRead(CongressionalDistrictImpactBase):
    """Schema for reading congressional district impacts."""

    id: UUID
    created_at: datetime
