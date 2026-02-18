"""User-simulation association model.

Associates users with simulations they've run. This enables users to
maintain a list of their simulations across sessions.

Note: user_id is a client-generated UUID (via crypto.randomUUID()) stored in
the browser's localStorage. It is NOT validated against a users table, allowing
anonymous users to save simulations without authentication.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from policyengine_api.config.constants import CountryId


class UserSimulationAssociationBase(SQLModel):
    """Base association fields."""

    user_id: UUID = Field(index=True)
    simulation_id: UUID = Field(foreign_key="simulations.id", index=True)
    country_id: str
    label: str | None = None


class UserSimulationAssociation(UserSimulationAssociationBase, table=True):
    """User-simulation association database model."""

    __tablename__ = "user_simulation_associations"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserSimulationAssociationCreate(SQLModel):
    """Schema for creating user-simulation associations."""

    user_id: UUID
    simulation_id: UUID
    country_id: CountryId
    label: str | None = None


class UserSimulationAssociationRead(UserSimulationAssociationBase):
    """Schema for reading user-simulation associations."""

    id: UUID
    created_at: datetime
    updated_at: datetime


class UserSimulationAssociationUpdate(SQLModel):
    """Schema for updating user-simulation associations."""

    model_config = {"extra": "forbid"}

    label: str | None = None
