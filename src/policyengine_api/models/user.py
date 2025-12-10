from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class UserBase(SQLModel):
    """Base user fields."""

    first_name: str
    last_name: str
    email: str = Field(unique=True, index=True)


class User(UserBase, table=True):
    """User database model."""

    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserCreate(UserBase):
    """Schema for creating users."""

    pass


class UserRead(UserBase):
    """Schema for reading users."""

    id: UUID
    created_at: datetime
