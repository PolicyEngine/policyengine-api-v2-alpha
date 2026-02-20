"""Intra-decile impact output model.

Stores the distribution of income change categories within each income
decile. Each row represents one decile (1-10) or the overall average
(decile=0), with five proportion columns summing to ~1.0.

The five categories classify households by their percentage income change:
  - lose_more_than_5pct:  change <= -5%
  - lose_less_than_5pct:  -5% < change <= -0.1%
  - no_change:            -0.1% < change <= 0.1%
  - gain_less_than_5pct:  0.1% < change <= 5%
  - gain_more_than_5pct:  change > 5%

Proportions are people-weighted (using household_count_people *
household_weight) so they reflect the share of people, not households.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class IntraDecileImpactBase(SQLModel):
    """Base intra-decile impact fields."""

    baseline_simulation_id: UUID = Field(foreign_key="simulations.id")
    reform_simulation_id: UUID = Field(foreign_key="simulations.id")
    report_id: UUID | None = Field(default=None, foreign_key="reports.id")
    decile_type: str = Field(default="income")  # "income" or "wealth"
    decile: int  # 1-10 for individual deciles, 0 for overall average
    lose_more_than_5pct: float | None = None
    lose_less_than_5pct: float | None = None
    no_change: float | None = None
    gain_less_than_5pct: float | None = None
    gain_more_than_5pct: float | None = None


class IntraDecileImpact(IntraDecileImpactBase, table=True):
    """Intra-decile impact database model."""

    __tablename__ = "intra_decile_impacts"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IntraDecileImpactCreate(IntraDecileImpactBase):
    """Schema for creating intra-decile impact records."""

    pass


class IntraDecileImpactRead(IntraDecileImpactBase):
    """Schema for reading intra-decile impact records."""

    id: UUID
    created_at: datetime
