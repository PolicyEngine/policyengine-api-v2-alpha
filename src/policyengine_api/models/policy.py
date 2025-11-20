from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, Field, SQLModel


class PolicyBase(SQLModel):
    """Base policy fields."""

    name: str
    description: str | None = None
    parameter_values: dict = Field(
        default_factory=dict, sa_column=Column(JSON)
    )  # Serialized parameter values


class Policy(PolicyBase, table=True):
    """Policy database model."""

    __tablename__ = "policies"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PolicyCreate(PolicyBase):
    """Schema for creating policies."""

    pass


class PolicyRead(PolicyBase):
    """Schema for reading policies."""

    id: UUID
    created_at: datetime
    updated_at: datetime
