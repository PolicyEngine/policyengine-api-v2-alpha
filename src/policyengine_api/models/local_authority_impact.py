"""UK local authority impact output model."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field

from .geographic_impact_base import GeographicImpactBase


class LocalAuthorityImpactBase(GeographicImpactBase):
    """Base local authority impact fields."""

    local_authority_code: str
    local_authority_name: str
    x: int
    y: int


class LocalAuthorityImpact(LocalAuthorityImpactBase, table=True):
    """Local authority impact database model."""

    __tablename__ = "local_authority_impacts"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LocalAuthorityImpactCreate(LocalAuthorityImpactBase):
    """Schema for creating local authority impacts."""

    pass


class LocalAuthorityImpactRead(LocalAuthorityImpactBase):
    """Schema for reading local authority impacts."""

    id: UUID
    created_at: datetime
