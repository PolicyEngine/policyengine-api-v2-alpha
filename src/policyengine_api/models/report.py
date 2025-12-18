from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlmodel import Column, Field, SQLModel, Text


class ReportStatus(str, Enum):
    """Report processing status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ReportBase(SQLModel):
    """Base report fields."""

    label: str
    description: str | None = None
    user_id: UUID | None = Field(default=None, foreign_key="users.id")
    markdown: str | None = Field(default=None, sa_column=Column(Text))
    parent_report_id: UUID | None = Field(default=None, foreign_key="reports.id")
    status: ReportStatus = ReportStatus.PENDING
    error_message: str | None = None
    baseline_simulation_id: UUID | None = Field(
        default=None, foreign_key="simulations.id"
    )
    reform_simulation_id: UUID | None = Field(
        default=None, foreign_key="simulations.id"
    )


class Report(ReportBase, table=True):
    """Report database model."""

    __tablename__ = "reports"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReportCreate(ReportBase):
    """Schema for creating reports."""

    pass


class ReportRead(ReportBase):
    """Schema for reading reports."""

    id: UUID
    created_at: datetime
