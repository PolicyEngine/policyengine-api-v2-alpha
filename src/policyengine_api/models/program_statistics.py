"""Program statistics output model."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class ProgramStatisticsBase(SQLModel):
    """Base program statistics fields."""

    baseline_simulation_id: UUID = Field(foreign_key="simulations.id")
    reform_simulation_id: UUID = Field(foreign_key="simulations.id")
    report_id: UUID | None = Field(default=None, foreign_key="reports.id")
    program_name: str
    entity: str
    is_tax: bool = False
    baseline_total: float | None = None
    reform_total: float | None = None
    change: float | None = None
    baseline_count: float | None = None
    reform_count: float | None = None
    winners: float | None = None
    losers: float | None = None


class ProgramStatistics(ProgramStatisticsBase, table=True):
    """Program statistics database model."""

    __tablename__ = "program_statistics"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProgramStatisticsCreate(ProgramStatisticsBase):
    """Schema for creating program statistics."""

    pass


class ProgramStatisticsRead(ProgramStatisticsBase):
    """Schema for reading program statistics."""

    id: UUID
    created_at: datetime
