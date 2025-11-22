from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, Field, SQLModel


class ChangeAggregateType(str, Enum):
    """Change aggregate calculation types."""

    SUM = "sum"
    MEAN = "mean"
    COUNT = "count"


class ChangeAggregateBase(SQLModel):
    """Base change aggregate fields."""

    baseline_simulation_id: UUID
    reform_simulation_id: UUID
    variable: str
    aggregate_type: ChangeAggregateType
    entity: str | None = None
    filter_config: dict = Field(default_factory=dict, sa_column=Column(JSON))
    change_geq: float | None = None
    change_leq: float | None = None
    result: float | None = None


class ChangeAggregate(ChangeAggregateBase, table=True):
    """Change aggregate database model."""

    __tablename__ = "change_aggregates"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChangeAggregateCreate(ChangeAggregateBase):
    """Schema for creating change aggregates."""

    pass


class ChangeAggregateRead(ChangeAggregateBase):
    """Schema for reading change aggregates."""

    id: UUID
    created_at: datetime
