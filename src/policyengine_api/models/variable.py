from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class VariableBase(SQLModel):
    """Base variable fields."""

    name: str
    entity: str
    description: str | None = None
    data_type: str | None = None  # Store as string representation
    tax_benefit_model_version_id: UUID


class Variable(VariableBase, table=True):
    """Variable database model."""

    __tablename__ = "variables"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VariableCreate(VariableBase):
    """Schema for creating variables."""

    pass


class VariableRead(VariableBase):
    """Schema for reading variables."""

    id: UUID
    created_at: datetime
