from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .tax_benefit_model_version import TaxBenefitModelVersion


class TaxBenefitModelBase(SQLModel):
    """Base tax-benefit model fields."""

    name: str  # e.g., "uk", "us"
    description: str | None = None


class TaxBenefitModel(TaxBenefitModelBase, table=True):
    """Tax-benefit model database model."""

    __tablename__ = "tax_benefit_models"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    versions: list["TaxBenefitModelVersion"] = Relationship(back_populates="model")


class TaxBenefitModelCreate(TaxBenefitModelBase):
    """Schema for creating tax-benefit models."""

    pass


class TaxBenefitModelRead(TaxBenefitModelBase):
    """Schema for reading tax-benefit models."""

    id: UUID
    created_at: datetime
