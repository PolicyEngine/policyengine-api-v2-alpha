"""User-report association model.

Associates users with reports they've created. This enables users to
maintain a list of their reports across sessions.

Note: user_id is a client-generated UUID (via crypto.randomUUID()) stored in
the browser's localStorage. It is NOT validated against a users table, allowing
anonymous users to save reports without authentication.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from policyengine_api.config.constants import CountryId


class UserReportAssociationBase(SQLModel):
    """Base association fields."""

    user_id: UUID = Field(index=True)
    report_id: UUID = Field(foreign_key="reports.id", index=True)
    country_id: str
    label: str | None = None
    last_run_at: datetime | None = None


class UserReportAssociation(UserReportAssociationBase, table=True):
    """User-report association database model."""

    __tablename__ = "user_report_associations"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserReportAssociationCreate(SQLModel):
    """Schema for creating user-report associations."""

    user_id: UUID
    report_id: UUID
    country_id: CountryId
    label: str | None = None
    last_run_at: datetime | None = None


class UserReportAssociationRead(UserReportAssociationBase):
    """Schema for reading user-report associations."""

    id: UUID
    created_at: datetime
    updated_at: datetime


class UserReportAssociationUpdate(SQLModel):
    """Schema for updating user-report associations."""

    model_config = {"extra": "forbid"}

    label: str | None = None
    last_run_at: datetime | None = None
