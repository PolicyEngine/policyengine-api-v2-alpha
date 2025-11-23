from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .parameter import Parameter
    from .tax_benefit_model import TaxBenefitModel
    from .variable import Variable


class TaxBenefitModelVersionBase(SQLModel):
    """Base tax-benefit model version fields."""

    model_id: UUID = Field(foreign_key="tax_benefit_models.id")
    version: str  # e.g., "1.0.0", "latest"
    description: str | None = None


class TaxBenefitModelVersion(TaxBenefitModelVersionBase, table=True):
    """Tax-benefit model version database model."""

    __tablename__ = "tax_benefit_model_versions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    model: "TaxBenefitModel" = Relationship(back_populates="versions")
    variables: list["Variable"] = Relationship(
        back_populates="tax_benefit_model_version"
    )
    parameters: list["Parameter"] = Relationship(
        back_populates="tax_benefit_model_version"
    )


class TaxBenefitModelVersionCreate(TaxBenefitModelVersionBase):
    """Schema for creating tax-benefit model versions."""

    pass


class TaxBenefitModelVersionRead(TaxBenefitModelVersionBase):
    """Schema for reading tax-benefit model versions."""

    id: UUID
    created_at: datetime
