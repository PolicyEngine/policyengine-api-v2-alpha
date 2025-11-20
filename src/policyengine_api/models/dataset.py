from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class DatasetBase(SQLModel):
    """Base dataset fields."""

    name: str
    description: str | None = None
    filepath: str
    year: int
    tax_benefit_model: str  # e.g., "uk_latest", "us_latest"


class Dataset(DatasetBase, table=True):
    """Dataset database model."""

    __tablename__ = "datasets"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DatasetCreate(DatasetBase):
    """Schema for creating datasets."""

    pass


class DatasetRead(DatasetBase):
    """Schema for reading datasets."""

    id: UUID
    created_at: datetime
    updated_at: datetime
