from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

from .parameter_value import ParameterValueWithName

if TYPE_CHECKING:
    from .parameter_value import ParameterValue
    from .tax_benefit_model import TaxBenefitModel


class PolicyBase(SQLModel):
    """Base policy fields."""

    name: str
    description: str | None = None
    tax_benefit_model_id: UUID = Field(foreign_key="tax_benefit_models.id", index=True)


class Policy(PolicyBase, table=True):
    """Policy database model."""

    __tablename__ = "policies"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    parameter_values: list["ParameterValue"] = Relationship(back_populates="policy")
    tax_benefit_model: "TaxBenefitModel" = Relationship()


class PolicyParameterValueInput(SQLModel):
    """Input schema for a parameter value when creating a policy."""

    parameter_id: UUID
    value_json: Any
    start_date: datetime
    end_date: datetime | None = None


class PolicyCreate(PolicyBase):
    """Schema for creating policies.

    When creating a policy with parameter values, provide a list of
    parameter value definitions. Each parameter value needs:
    - parameter_id: UUID of the parameter to modify
    - value_json: The new value (number, string, or nested object)
    - start_date: When this value takes effect
    - end_date: Optional end date (null for indefinite)

    Example:
    {
        "name": "Lower basic rate to 16p",
        "description": "Reduce UK basic income tax rate",
        "parameter_values": [{
            "parameter_id": "uuid-here",
            "value_json": 0.16,
            "start_date": "2026-01-01T00:00:00Z",
            "end_date": null
        }]
    }
    """

    parameter_values: list[PolicyParameterValueInput] = []


class PolicyRead(PolicyBase):
    """Schema for reading policies."""

    id: UUID
    created_at: datetime
    updated_at: datetime
    parameter_values: list[ParameterValueWithName] = []
