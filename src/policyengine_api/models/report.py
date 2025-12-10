from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel, Text, Column


class ReportBase(SQLModel):
    """Base report fields."""

    label: str
    description: str | None = None
    user_id: UUID = Field(foreign_key="users.id")
    markdown: str | None = Field(default=None, sa_column=Column(Text))
    parent_report_id: UUID | None = Field(default=None, foreign_key="reports.id")


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
