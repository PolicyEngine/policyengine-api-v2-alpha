from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from pydantic import model_validator
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSON
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .dataset import Dataset
    from .dynamic import Dynamic
    from .household import Household
    from .policy import Policy
    from .region import Region
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

    # Region provenance (which region this simulation targets)
    region_id: UUID | None = Field(default=None, foreign_key="regions.id")

    # Regional filtering parameters (passed to policyengine.py)
    filter_field: str | None = Field(
        default=None,
        description="Household-level variable to filter dataset by (e.g., 'place_fips', 'country')",
    )
    filter_value: str | None = Field(
        default=None,
        description="Value to match when filtering (e.g., '44000', 'ENGLAND')",
    )
    filter_strategy: str | None = Field(
        default=None,
        description="Scoping strategy: 'row_filter' or 'weight_replacement'",
    )

    year: int | None = None


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
    region: "Region" = Relationship()
    dynamic: "Dynamic" = Relationship()
    tax_benefit_model_version: "TaxBenefitModelVersion" = Relationship()
    output_dataset: "Dataset" = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[Simulation.output_dataset_id]",
            "primaryjoin": "Simulation.output_dataset_id==Dataset.id",
        }
    )


class SimulationCreate(SQLModel):
    """Schema for creating simulations — client-settable fields only.

    Excludes server-controlled fields: status, error_message, output_dataset_id.
    """

    simulation_type: SimulationType = SimulationType.ECONOMY
    dataset_id: UUID | None = None
    household_id: UUID | None = None
    policy_id: UUID | None = None
    dynamic_id: UUID | None = None
    tax_benefit_model_version_id: UUID
    region_id: UUID | None = None
    filter_field: str | None = None
    filter_value: str | None = None
    filter_strategy: str | None = None
    year: int | None = None

    @model_validator(mode="after")
    def check_type_consistency(self) -> "SimulationCreate":
        if self.simulation_type == SimulationType.HOUSEHOLD:
            if not self.household_id:
                raise ValueError("HOUSEHOLD simulation requires household_id")
            if self.dataset_id:
                raise ValueError("HOUSEHOLD simulation cannot have dataset_id")
        elif self.simulation_type == SimulationType.ECONOMY:
            if not self.dataset_id:
                raise ValueError("ECONOMY simulation requires dataset_id")
            if self.household_id:
                raise ValueError("ECONOMY simulation cannot have household_id")
        if (self.filter_field is None) != (self.filter_value is None):
            raise ValueError(
                "filter_field and filter_value must both be set or both None"
            )
        return self


class SimulationRead(SimulationBase):
    """Schema for reading simulations."""

    id: UUID
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    household_result: dict[str, Any] | None = None
