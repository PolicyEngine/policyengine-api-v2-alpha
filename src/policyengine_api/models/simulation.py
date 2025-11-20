from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class SimulationStatus(str, Enum):
    """Simulation execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SimulationBase(SQLModel):
    """Base simulation fields."""

    dataset_id: UUID
    policy_id: UUID | None = None
    tax_benefit_model: str  # e.g., "uk_latest", "us_latest"
    status: SimulationStatus = SimulationStatus.PENDING
    error_message: str | None = None


class Simulation(SimulationBase, table=True):
    """Simulation database model."""

    __tablename__ = "simulations"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None


class SimulationCreate(SimulationBase):
    """Schema for creating simulations."""

    pass


class SimulationRead(SimulationBase):
    """Schema for reading simulations."""

    id: UUID
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
