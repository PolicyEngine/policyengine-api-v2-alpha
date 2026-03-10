from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .tax_benefit_model_version import TaxBenefitModelVersion


class ParameterNodeBase(SQLModel):
    """Base parameter node fields.

    Parameter nodes represent folder/category structure in the parameter tree,
    as opposed to leaf parameters which hold actual values.
    """

    name: str  # Full path, e.g., "gov.hmrc"
    label: str | None = None  # Human-readable label, e.g., "HMRC"
    description: str | None = None
    tax_benefit_model_version_id: UUID = Field(
        foreign_key="tax_benefit_model_versions.id"
    )


class ParameterNode(ParameterNodeBase, table=True):
    """Parameter node database model."""

    __tablename__ = "parameter_nodes"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    tax_benefit_model_version: "TaxBenefitModelVersion" = Relationship(
        back_populates="parameter_nodes"
    )


class ParameterNodeCreate(ParameterNodeBase):
    """Schema for creating parameter nodes."""

    pass


class ParameterNodeRead(ParameterNodeBase):
    """Schema for reading parameter nodes."""

    id: UUID
    created_at: datetime
