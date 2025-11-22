from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .tax_benefit_model_version import TaxBenefitModelVersion


class VariableBase(SQLModel):
    """Base variable fields."""

    name: str
    entity: str
    description: str | None = None
    data_type: str | None = None  # Store as string representation
    possible_values: str | None = Field(
        default=None, sa_column=Column(JSON)
    )  # Store as JSON list
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
