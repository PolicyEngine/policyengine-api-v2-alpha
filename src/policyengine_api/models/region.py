"""Region model for geographic areas used in analysis."""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import sqlalchemy as sa
from pydantic import model_validator
from sqlmodel import Field, Relationship, SQLModel

from .region_dataset_link import RegionDatasetLink

if TYPE_CHECKING:
    from .dataset import Dataset
    from .tax_benefit_model import TaxBenefitModel


class RegionType(str, Enum):
    """Type of geographic region."""

    NATIONAL = "national"
    COUNTRY = "country"
    STATE = "state"
    CONGRESSIONAL_DISTRICT = "congressional_district"
    CONSTITUENCY = "constituency"
    LOCAL_AUTHORITY = "local_authority"
    CITY = "city"
    PLACE = "place"


class RegionBase(SQLModel):
    """Base region fields."""

    code: str  # e.g., "state/ca", "constituency/Sheffield Central"
    label: str  # e.g., "California", "Sheffield Central"
    region_type: RegionType = Field(
        sa_type=sa.Enum(RegionType, values_callable=lambda x: [e.value for e in x]),
    )
    requires_filter: bool = False
    filter_field: str | None = None  # e.g., "state_code", "place_fips"
    filter_value: str | None = None  # e.g., "CA", "44000"
    parent_code: str | None = None  # e.g., "us", "state/ca"
    state_code: str | None = None  # For US regions
    state_name: str | None = None  # For US regions
    tax_benefit_model_id: UUID = Field(foreign_key="tax_benefit_models.id")


class Region(RegionBase, table=True):
    """Region database model.

    Regions represent geographic areas for analysis, from countries
    down to states, congressional districts, cities, etc.
    Each region links to multiple datasets (one per year) via the
    region_datasets join table.
    """

    __tablename__ = "regions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    datasets: list["Dataset"] = Relationship(link_model=RegionDatasetLink)
    tax_benefit_model: "TaxBenefitModel" = Relationship()


class RegionCreate(RegionBase):
    """Schema for creating regions."""

    @model_validator(mode="after")
    def check_filter_fields(self) -> "RegionCreate":
        if self.requires_filter:
            if not self.filter_field or not self.filter_value:
                raise ValueError(
                    "requires_filter=True requires filter_field and filter_value"
                )
        return self


class RegionRead(RegionBase):
    """Schema for reading regions."""

    id: UUID
    created_at: datetime
    updated_at: datetime
