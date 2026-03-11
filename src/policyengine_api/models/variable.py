from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .tax_benefit_model_version import TaxBenefitModelVersion


class VariableBase(SQLModel):
    """Base variable fields."""

    name: str
    label: str | None = None
    entity: str
    description: str | None = None
    data_type: str | None = None  # Store as string representation
    possible_values: list[str] | None = Field(
        default=None, sa_column=Column(JSON)
    )  # Store as JSON list
    default_value: Any = Field(
        default=None, sa_column=Column(JSON)
    )  # Store as JSON (handles int, float, bool, str, etc.)
    adds: list[str] | None = Field(
        default=None, sa_column=Column(JSON)
    )  # Variable names that are added to compute this variable
    subtracts: list[str] | None = Field(
        default=None, sa_column=Column(JSON)
    )  # Variable names that are subtracted to compute this variable
    tax_benefit_model_version_id: UUID = Field(
        foreign_key="tax_benefit_model_versions.id"
    )


class Variable(VariableBase, table=True):
    """Variable database model."""

    __tablename__ = "variables"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    tax_benefit_model_version: "TaxBenefitModelVersion" = Relationship(
        back_populates="variables"
    )


class VariableCreate(VariableBase):
    """Schema for creating variables."""

    pass


class VariableRead(VariableBase):
    """Schema for reading variables."""

    id: UUID
    created_at: datetime
