"""Congressional district impact output model."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field

from .geographic_impact_base import GeographicImpactBase


class CongressionalDistrictImpactBase(GeographicImpactBase):
    """Base congressional district impact fields."""

    district_geoid: int
    state_fips: int
    district_number: int


class CongressionalDistrictImpact(CongressionalDistrictImpactBase, table=True):
    """Congressional district impact database model."""

    __tablename__ = "congressional_district_impacts"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CongressionalDistrictImpactCreate(CongressionalDistrictImpactBase):
    """Schema for creating congressional district impacts."""

    pass


class CongressionalDistrictImpactRead(CongressionalDistrictImpactBase):
    """Schema for reading congressional district impacts."""

    id: UUID
    created_at: datetime
