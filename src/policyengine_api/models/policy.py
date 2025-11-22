from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .parameter_value import ParameterValue


class PolicyBase(SQLModel):
    """Base policy fields."""

    name: str
    description: str | None = None


class Policy(PolicyBase, table=True):
    """Policy database model."""

    __tablename__ = "policies"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    parameter_values: list["ParameterValue"] = Relationship(back_populates="policy")


class PolicyCreate(PolicyBase):
    """Schema for creating policies."""

    pass


class PolicyRead(PolicyBase):
    """Schema for reading policies."""

    id: UUID
    created_at: datetime
    updated_at: datetime
