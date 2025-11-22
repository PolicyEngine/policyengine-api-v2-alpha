from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .parameter_value import ParameterValue


class DynamicBase(SQLModel):
    """Base dynamic fields."""

    name: str
    description: str | None = None


class Dynamic(DynamicBase, table=True):
    """Dynamic database model."""

    __tablename__ = "dynamics"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    parameter_values: list["ParameterValue"] = Relationship(back_populates="dynamic")


class DynamicCreate(DynamicBase):
    """Schema for creating dynamics."""

    pass


class DynamicRead(DynamicBase):
    """Schema for reading dynamics."""

    id: UUID
    created_at: datetime
    updated_at: datetime
