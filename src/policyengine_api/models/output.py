from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, Field, SQLModel


class AggregateType(str, Enum):
    """Aggregate calculation types."""

    SUM = "sum"
    MEAN = "mean"
    COUNT = "count"


class AggregateOutputBase(SQLModel):
    """Base aggregate output fields."""

    simulation_id: UUID
    variable: str
    aggregate_type: AggregateType
    entity: str | None = None
    filter_config: dict = Field(
        default_factory=dict, sa_column=Column(JSON)
    )  # Filter parameters
    result: float | None = None


class AggregateOutput(AggregateOutputBase, table=True):
    """Aggregate output database model."""

    __tablename__ = "aggregate_outputs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AggregateOutputCreate(AggregateOutputBase):
    """Schema for creating aggregate outputs."""

    pass


class AggregateOutputRead(AggregateOutputBase):
    """Schema for reading aggregate outputs."""

    id: UUID
    created_at: datetime
