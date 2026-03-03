"""User-household association model."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from policyengine_api.config.constants import CountryId


class UserHouseholdAssociationBase(SQLModel):
    """Base association fields."""

    # user_id is a client-generated UUID stored in localStorage, not a foreign key
    user_id: UUID = Field(index=True)
    household_id: UUID = Field(foreign_key="households.id", index=True)
    country_id: str  # Stored as string in DB, validated via Pydantic in Create schema
    label: str | None = None


class UserHouseholdAssociation(UserHouseholdAssociationBase, table=True):
    """User-household association database model."""

    __tablename__ = "user_household_associations"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserHouseholdAssociationCreate(SQLModel):
    """Schema for creating a user-household association."""

    user_id: UUID
    household_id: UUID
    country_id: CountryId
    label: str | None = None


class UserHouseholdAssociationUpdate(SQLModel):
    """Schema for updating a user-household association."""

    model_config = {"extra": "forbid"}

    label: str | None = None


class UserHouseholdAssociationRead(UserHouseholdAssociationBase):
    """Schema for reading a user-household association."""

    id: UUID
    created_at: datetime
    updated_at: datetime
