from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, Field, SQLModel


class AggregateType(str, Enum):
    """Aggregate calculation types."""

    SUM = "sum"
    MEAN = "mean"
    COUNT = "count"


class AggregateStatus(str, Enum):
    """Aggregate execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AggregateOutputBase(SQLModel):
    """Base aggregate fields."""

    simulation_id: UUID = Field(foreign_key="simulations.id")
    user_id: UUID | None = Field(default=None, foreign_key="users.id")
    report_id: UUID | None = Field(default=None, foreign_key="reports.id")
    variable: str
    aggregate_type: AggregateType
    entity: str | None = None
    filter_config: dict = Field(
        default_factory=dict, sa_column=Column(JSON)
    )  # Filter parameters
    status: AggregateStatus = AggregateStatus.PENDING
    error_message: str | None = None
    result: float | None = None


class AggregateOutput(AggregateOutputBase, table=True):
    """Aggregate database model."""

    __tablename__ = "aggregates"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AggregateOutputCreate(AggregateOutputBase):
    """Schema for creating aggregates."""

    pass


class AggregateOutputRead(AggregateOutputBase):
    """Schema for reading aggregates."""

    id: UUID
    created_at: datetime
