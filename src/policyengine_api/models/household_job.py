"""Household calculation job model for async processing."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON
from sqlmodel import Column, Field, SQLModel


class HouseholdJobStatus(str, Enum):
    """Household job execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class HouseholdJobBase(SQLModel):
    """Base household job fields."""

    tax_benefit_model_name: str
    request_data: dict[str, Any] = Field(sa_column=Column(JSON))
    policy_id: UUID | None = Field(default=None, foreign_key="policies.id")
    dynamic_id: UUID | None = Field(default=None, foreign_key="dynamics.id")
    status: HouseholdJobStatus = HouseholdJobStatus.PENDING
    error_message: str | None = None
    result: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))


class HouseholdJob(HouseholdJobBase, table=True):
    """Household job database model."""

    __tablename__ = "household_jobs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None


class HouseholdJobCreate(HouseholdJobBase):
    """Schema for creating household jobs."""

    pass


class HouseholdJobRead(HouseholdJobBase):
    """Schema for reading household jobs."""

    id: UUID
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
