from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .dataset import Dataset
    from .policy import Policy
    from .dynamic import Dynamic
    from .tax_benefit_model_version import TaxBenefitModelVersion


class SimulationStatus(str, Enum):
    """Simulation execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SimulationBase(SQLModel):
    """Base simulation fields."""

    dataset_id: UUID = Field(foreign_key="datasets.id")
    policy_id: UUID | None = Field(default=None, foreign_key="policies.id")
    dynamic_id: UUID | None = Field(default=None, foreign_key="dynamics.id")
    tax_benefit_model_version_id: UUID = Field(
        foreign_key="tax_benefit_model_versions.id"
    )
    output_dataset_id: UUID | None = Field(default=None, foreign_key="datasets.id")
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

    # Relationships
    dataset: "Dataset" = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[Simulation.dataset_id]",
            "primaryjoin": "Simulation.dataset_id==Dataset.id",
        }
    )
    policy: "Policy" = Relationship()
    dynamic: "Dynamic" = Relationship()
    tax_benefit_model_version: "TaxBenefitModelVersion" = Relationship()
    output_dataset: "Dataset" = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[Simulation.output_dataset_id]",
            "primaryjoin": "Simulation.output_dataset_id==Dataset.id",
        }
    )


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
