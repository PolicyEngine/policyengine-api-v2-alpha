from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class ParameterBase(SQLModel):
    """Base parameter fields."""

    name: str
    description: str | None = None
    data_type: str | None = None
    unit: str | None = None
    tax_benefit_model_version_id: UUID


class Parameter(ParameterBase, table=True):
    """Parameter database model."""

    __tablename__ = "parameters"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ParameterCreate(ParameterBase):
    """Schema for creating parameters."""

    pass


class ParameterRead(ParameterBase):
    """Schema for reading parameters."""

    id: UUID
    created_at: datetime
