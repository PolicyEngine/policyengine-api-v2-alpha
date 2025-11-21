from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, Field, SQLModel


class ParameterValueBase(SQLModel):
    """Base parameter value fields."""

    parameter_id: UUID = Field(foreign_key="parameters.id")
    value: dict = Field(default_factory=dict, sa_column=Column(JSON))  # Store as JSON
    start_date: datetime
    end_date: datetime | None = None


class ParameterValue(ParameterValueBase, table=True):
    """Parameter value database model."""

    __tablename__ = "parameter_values"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ParameterValueCreate(ParameterValueBase):
    """Schema for creating parameter values."""

    pass


class ParameterValueRead(ParameterValueBase):
    """Schema for reading parameter values."""

    id: UUID
    created_at: datetime
