from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .dataset import Dataset
    from .tax_benefit_model import TaxBenefitModel


class DatasetVersionBase(SQLModel):
    """Base dataset version fields."""

    name: str  # Version name like "v1.0", "enhanced_2024"
    description: str
    dataset_id: UUID = Field(foreign_key="datasets.id")
    tax_benefit_model_id: UUID = Field(foreign_key="tax_benefit_models.id")


class DatasetVersion(DatasetVersionBase, table=True):
    """Dataset version database model."""

    __tablename__ = "dataset_versions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    dataset: "Dataset" = Relationship(back_populates="versions")
    tax_benefit_model: "TaxBenefitModel" = Relationship()


class DatasetVersionCreate(DatasetVersionBase):
    """Schema for creating dataset versions."""

    pass


class DatasetVersionRead(DatasetVersionBase):
    """Schema for reading dataset versions."""

    id: UUID
    created_at: datetime
