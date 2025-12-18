from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .dynamic import Dynamic
    from .parameter import Parameter
    from .policy import Policy


class ParameterValueBase(SQLModel): 
    """Base parameter value fields."""

    parameter_id: UUID = Field(foreign_key="parameters.id")
    value_json: str = Field(sa_column=Column(JSON))  # Polymorphic value storage
    start_date: datetime
    end_date: datetime | None = None

    # Optional foreign keys - a ParameterValue can belong to Policy, Dynamic, or neither
    policy_id: UUID | None = Field(default=None, foreign_key="policies.id")
    dynamic_id: UUID | None = Field(default=None, foreign_key="dynamics.id")


class ParameterValue(ParameterValueBase, table=True):
    """Parameter value database model."""

    __tablename__ = "parameter_values"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    parameter: "Parameter" = Relationship(back_populates="parameter_values")
    policy: "Policy" = Relationship(back_populates="parameter_values")
    dynamic: "Dynamic" = Relationship(back_populates="parameter_values")


class ParameterValueCreate(ParameterValueBase):
    """Schema for creating parameter values."""

    pass


class ParameterValueRead(ParameterValueBase):
    """Schema for reading parameter values."""

    id: UUID
    created_at: datetime
