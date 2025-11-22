from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .tax_benefit_model_version import TaxBenefitModelVersion
    from .parameter_value import ParameterValue


class ParameterBase(SQLModel):
    """Base parameter fields."""

    name: str
    label: str | None = None
    description: str | None = None
    data_type: str | None = None
    unit: str | None = None
    tax_benefit_model_version_id: UUID = Field(foreign_key="tax_benefit_model_versions.id")


class Parameter(ParameterBase, table=True):
    """Parameter database model."""

    __tablename__ = "parameters"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    tax_benefit_model_version: "TaxBenefitModelVersion" = Relationship(
        back_populates="parameters"
    )
    parameter_values: list["ParameterValue"] = Relationship(back_populates="parameter")


class ParameterCreate(ParameterBase):
    """Schema for creating parameters."""

    pass


class ParameterRead(ParameterBase):
    """Schema for reading parameters."""

    id: UUID
    created_at: datetime
