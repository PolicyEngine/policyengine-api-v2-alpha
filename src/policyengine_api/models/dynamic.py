from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, Field, SQLModel


class DynamicBase(SQLModel):
    """Base dynamic fields."""

    name: str
    description: str | None = None
    parameter_values: dict = Field(
        default_factory=dict, sa_column=Column(JSON)
    )  # Serialized


class Dynamic(DynamicBase, table=True):
    """Dynamic database model."""

    __tablename__ = "dynamics"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DynamicCreate(DynamicBase):
    """Schema for creating dynamics."""

    pass


class DynamicRead(DynamicBase):
    """Schema for reading dynamics."""

    id: UUID
    created_at: datetime
    updated_at: datetime
