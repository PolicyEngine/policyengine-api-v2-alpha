"""Budget summary output model.

Stores economy-wide fiscal aggregates for a report. Each row represents
a single aggregate variable (e.g. household_tax, household_benefits)
with baseline and reform totals. This is separate from ProgramStatistics,
which stores per-program breakdowns.

The client can derive V1-compatible budget fields from these rows:
  - tax_revenue_impact      = household_tax row's change
  - benefit_spending_impact  = household_benefits row's change
  - budgetary_impact         = tax change - benefit change
  - households               = household_count_total row's baseline_total
  - baseline_net_income      = household_net_income row's baseline_total
  - state_tax_revenue_impact = household_state_income_tax row's change (US only)
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class BudgetSummaryBase(SQLModel):
    """Base budget summary fields."""

    baseline_simulation_id: UUID = Field(foreign_key="simulations.id")
    reform_simulation_id: UUID = Field(foreign_key="simulations.id")
    report_id: UUID | None = Field(default=None, foreign_key="reports.id")
    variable_name: str
    entity: str
    baseline_total: float | None = None
    reform_total: float | None = None
    change: float | None = None


class BudgetSummary(BudgetSummaryBase, table=True):
    """Budget summary database model."""

    __tablename__ = "budget_summary"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BudgetSummaryCreate(BudgetSummaryBase):
    """Schema for creating budget summary records."""

    pass


class BudgetSummaryRead(BudgetSummaryBase):
    """Schema for reading budget summary records."""

    id: UUID
    created_at: datetime
