"""Shared base for geographic impact models."""

from uuid import UUID

from sqlmodel import Field, SQLModel


class GeographicImpactBase(SQLModel):
    """Shared fields for geographic impact models.

    Used by constituency, local authority, and congressional district impacts.
    """

    baseline_simulation_id: UUID = Field(foreign_key="simulations.id")
    reform_simulation_id: UUID = Field(foreign_key="simulations.id")
    report_id: UUID | None = Field(default=None, foreign_key="reports.id")
    average_household_income_change: float
    relative_household_income_change: float
    population: float
