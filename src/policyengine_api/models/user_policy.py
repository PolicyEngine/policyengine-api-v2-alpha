from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .policy import Policy


class UserPolicyBase(SQLModel):
    """Base user-policy association fields."""

    # user_id is a client-generated UUID stored in localStorage, not a foreign key.
    # This allows anonymous users to save policies without requiring authentication.
    # The UUID is generated once per browser via crypto.randomUUID() and persisted
    # in localStorage for stable identity across sessions.
    user_id: UUID = Field(index=True)
    policy_id: UUID = Field(foreign_key="policies.id", index=True)
    country_id: str  # e.g., "us", "uk" - denormalized for efficient filtering
    label: str | None = None


class UserPolicy(UserPolicyBase, table=True):
    """User-policy association database model."""

    __tablename__ = "user_policies"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    policy: "Policy" = Relationship()


class UserPolicyCreate(UserPolicyBase):
    """Schema for creating user-policy associations."""

    pass


class UserPolicyRead(UserPolicyBase):
    """Schema for reading user-policy associations."""

    id: UUID
    created_at: datetime
    updated_at: datetime


class UserPolicyUpdate(SQLModel):
    """Schema for updating user-policy associations."""

    label: str | None = None
