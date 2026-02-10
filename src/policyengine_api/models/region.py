"""Region model for geographic areas used in analysis."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .dataset import Dataset
    from .tax_benefit_model import TaxBenefitModel


class RegionBase(SQLModel):
    """Base region fields."""

    code: str  # e.g., "state/ca", "constituency/Sheffield Central"
    label: str  # e.g., "California", "Sheffield Central"
    region_type: str  # e.g., "state", "congressional_district", "constituency"
    requires_filter: bool = False
    filter_field: str | None = None  # e.g., "state_code", "place_fips"
    filter_value: str | None = None  # e.g., "CA", "44000"
    parent_code: str | None = None  # e.g., "us", "state/ca"
    state_code: str | None = None  # For US regions
    state_name: str | None = None  # For US regions
    dataset_id: UUID = Field(foreign_key="datasets.id")
    tax_benefit_model_id: UUID = Field(foreign_key="tax_benefit_models.id")


class Region(RegionBase, table=True):
    """Region database model.

    Regions represent geographic areas for analysis, from countries
    down to states, congressional districts, cities, etc.
    Each region has a dataset (either dedicated or filtered from parent).
    """

    __tablename__ = "regions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    dataset: "Dataset" = Relationship()
    tax_benefit_model: "TaxBenefitModel" = Relationship()


class RegionCreate(RegionBase):
    """Schema for creating regions."""

    pass


class RegionRead(RegionBase):
    """Schema for reading regions."""

    id: UUID
    created_at: datetime
    updated_at: datetime
