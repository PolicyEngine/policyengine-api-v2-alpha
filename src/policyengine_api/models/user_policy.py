from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .policy import Policy
    from .user import User


class UserPolicyBase(SQLModel):
    """Base user-policy association fields."""

    user_id: UUID = Field(foreign_key="users.id", index=True)
    policy_id: UUID = Field(foreign_key="policies.id", index=True)
    country_id: str  # "us" or "uk"
    label: str | None = None


class UserPolicy(UserPolicyBase, table=True):
    """User-policy association database model."""

    __tablename__ = "user_policies"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    user: "User" = Relationship()
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
