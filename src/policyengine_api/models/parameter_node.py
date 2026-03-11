from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .tax_benefit_model_version import TaxBenefitModelVersion


class ParameterNodeBase(SQLModel):
    """Base parameter node fields.

    Parameter nodes represent folder/category nodes in the parameter hierarchy
    (e.g., "gov", "gov.hmrc", "gov.hmrc.income_tax"). They provide structure
    and human-readable labels for navigating the parameter tree, but don't
    have values themselves.
    """

    name: str = Field(description="Full path of the node (e.g., 'gov.hmrc')")
    label: str | None = Field(
        default=None, description="Human-readable label (e.g., 'HMRC')"
    )
    description: str | None = Field(default=None, description="Node description")
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
