from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSON
from sqlmodel import Field, Relationship, SQLModel
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from .dataset import Dataset
    from .dynamic import Dynamic
    from .household import Household
    from .policy import Policy
    from .tax_benefit_model_version import TaxBenefitModelVersion


class SimulationStatus(str, Enum):
    """Simulation execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SimulationType(str, Enum):
    """Type of simulation."""

    HOUSEHOLD = "household"
    ECONOMY = "economy"


class SimulationBase(SQLModel):
    """Base simulation fields."""

    simulation_type: SimulationType = SimulationType.ECONOMY
    dataset_id: UUID | None = Field(default=None, foreign_key="datasets.id")
    household_id: UUID | None = Field(default=None, foreign_key="households.id")
    policy_id: UUID | None = Field(default=None, foreign_key="policies.id")
    dynamic_id: UUID | None = Field(default=None, foreign_key="dynamics.id")
    tax_benefit_model_version_id: UUID = Field(
        foreign_key="tax_benefit_model_versions.id"
    )
    output_dataset_id: UUID | None = Field(default=None, foreign_key="datasets.id")
    status: SimulationStatus = SimulationStatus.PENDING
    error_message: str | None = None

    # Regional filtering parameters (passed to policyengine.py)
    filter_field: str | None = Field(
        default=None,
        description="Household-level variable to filter dataset by (e.g., 'place_fips', 'country')",
    )
    filter_value: str | None = Field(
        default=None,
        description="Value to match when filtering (e.g., '44000', 'ENGLAND')",
    )


class Simulation(SimulationBase, table=True):
    """Simulation database model."""

    __tablename__ = "simulations"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    household_result: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON)
    )

    # Relationships
    dataset: "Dataset" = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[Simulation.dataset_id]",
            "primaryjoin": "Simulation.dataset_id==Dataset.id",
        }
    )
    household: "Household" = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[Simulation.household_id]",
            "primaryjoin": "Simulation.household_id==Household.id",
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
    household_result: dict[str, Any] | None = None
