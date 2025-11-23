from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .dataset_version import DatasetVersion
    from .tax_benefit_model import TaxBenefitModel


class DatasetBase(SQLModel):
    """Base dataset fields."""

    name: str
    description: str | None = None
    filepath: str  # S3 path in Supabase storage for h5 file
    year: int
    is_output_dataset: bool = False
    tax_benefit_model_id: UUID = Field(foreign_key="tax_benefit_models.id")


class Dataset(DatasetBase, table=True):
    """Dataset database model.

    Datasets are stored as h5 files in Supabase S3 storage.
    The policyengine package has save() and load() functionality
    that needs to be integrated with S3 upload/download.
    """

    __tablename__ = "datasets"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    tax_benefit_model: "TaxBenefitModel" = Relationship()
    versions: list["DatasetVersion"] = Relationship(back_populates="dataset")


class DatasetCreate(DatasetBase):
    """Schema for creating datasets."""

    pass


class DatasetRead(DatasetBase):
    """Schema for reading datasets."""

    id: UUID
    created_at: datetime
    updated_at: datetime
