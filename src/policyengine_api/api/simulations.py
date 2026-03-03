"""Simulation endpoints.

Simulations are individual tax-benefit calculations. Use these endpoints to:
- Create and run household simulations (single household, single policy)
- Create and run economy simulations (population dataset, single policy)
- Check simulation status and retrieve results

For baseline-vs-reform comparisons, use the /analysis/ endpoints instead.
"""

from typing import Any, List, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from policyengine_api.models import (
    Dataset,
    Household,
    Policy,
    Region,
    RegionDatasetLink,
    Simulation,
    SimulationRead,
    SimulationStatus,
    SimulationType,
    TaxBenefitModel,
)
from policyengine_api.services.database import get_session

from .analysis import (
    RegionInfo,
    _get_model_version,
    _get_or_create_simulation,
)

router = APIRouter(prefix="/simulations", tags=["simulations"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class HouseholdSimulationRequest(BaseModel):
    """Request body for creating a household simulation."""

    household_id: UUID = Field(description="ID of the stored household")
    policy_id: UUID | None = Field(
        default=None,
        description="Reform policy ID. If None, runs under current law.",
    )
    dynamic_id: UUID | None = Field(
        default=None,
        description="Optional behavioural response specification ID",
    )


class HouseholdSimulationResponse(BaseModel):
    """Response for a household simulation."""

    id: UUID
    status: SimulationStatus
    household_id: UUID | None = None
    policy_id: UUID | None = None
    household_result: dict[str, Any] | None = None
    error_message: str | None = None


class EconomySimulationRequest(BaseModel):
    """Request body for creating an economy simulation."""

    tax_benefit_model_name: Literal["policyengine_uk", "policyengine_us"] = Field(
        description="Which country model to use"
    )
    region: str | None = Field(
        default=None,
        description="Region code (e.g., 'state/ca', 'us'). Either region or dataset_id must be provided.",
    )
    dataset_id: UUID | None = Field(
        default=None,
        description="Dataset ID. Either region or dataset_id must be provided.",
    )
    policy_id: UUID | None = Field(
        default=None,
        description="Reform policy ID. If None, runs under current law.",
    )
    dynamic_id: UUID | None = Field(
        default=None,
        description="Optional behavioural response specification ID",
    )
    year: int | None = Field(
        default=None,
        description="Year for the simulation. Uses latest available if omitted.",
    )


class EconomySimulationResponse(BaseModel):
    """Response for an economy simulation."""

    id: UUID
    status: SimulationStatus
    dataset_id: UUID | None = None
    policy_id: UUID | None = None
    output_dataset_id: UUID | None = None
    filter_field: str | None = None
    filter_value: str | None = None
    region: RegionInfo | None = None
    error_message: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_economy_dataset(
    tax_benefit_model_name: str,
    region_code: str | None,
    dataset_id: UUID | None,
    session: Session,
    year: int | None = None,
) -> tuple[Dataset, Region | None]:
    """Resolve dataset from region code or dataset_id for economy simulations.

    When a region is provided, the dataset is resolved from the region_datasets
    join table. If year is set, the dataset for that year is selected;
    otherwise the latest available year is used.
    """
    if region_code:
        model_name = tax_benefit_model_name.replace("_", "-")
        region = session.exec(
            select(Region)
            .join(TaxBenefitModel)
            .where(Region.code == region_code)
            .where(TaxBenefitModel.name == model_name)
        ).first()
        if not region:
            raise HTTPException(
                status_code=404,
                detail=f"Region '{region_code}' not found for model {model_name}",
            )

        # Resolve dataset from join table
        query = (
            select(Dataset)
            .join(RegionDatasetLink)
            .where(RegionDatasetLink.region_id == region.id)
        )
        if year:
            query = query.where(Dataset.year == year)
        else:
            query = query.order_by(Dataset.year.desc())  # type: ignore
        dataset = session.exec(query).first()

        if not dataset:
            year_msg = f" for year {year}" if year else ""
            raise HTTPException(
                status_code=404,
                detail=f"No dataset found for region '{region_code}'{year_msg}",
            )
        return dataset, region

    elif dataset_id:
        dataset = session.get(Dataset, dataset_id)
        if not dataset:
            raise HTTPException(
                status_code=404,
                detail=f"Dataset {dataset_id} not found",
            )
        return dataset, None

    else:
        raise HTTPException(
            status_code=400,
            detail="Either region or dataset_id must be provided",
        )


def _build_household_response(simulation: Simulation) -> HouseholdSimulationResponse:
    """Build response from a household simulation."""
    return HouseholdSimulationResponse(
        id=simulation.id,
        status=simulation.status,
        household_id=simulation.household_id,
        policy_id=simulation.policy_id,
        household_result=simulation.household_result,
        error_message=simulation.error_message,
    )


def _build_economy_response(
    simulation: Simulation, region: Region | None = None
) -> EconomySimulationResponse:
    """Build response from an economy simulation."""
    region_info = None
    if region:
        region_info = RegionInfo(
            code=region.code,
            label=region.label,
            region_type=region.region_type,
            requires_filter=region.requires_filter,
            filter_field=region.filter_field,
            filter_value=region.filter_value,
        )

    return EconomySimulationResponse(
        id=simulation.id,
        status=simulation.status,
        dataset_id=simulation.dataset_id,
        policy_id=simulation.policy_id,
        output_dataset_id=simulation.output_dataset_id,
        filter_field=simulation.filter_field,
        filter_value=simulation.filter_value,
        region=region_info,
        error_message=simulation.error_message,
    )


# ---------------------------------------------------------------------------
# List / generic get (existing endpoints)
# ---------------------------------------------------------------------------


@router.get("/", response_model=List[SimulationRead])
def list_simulations(session: Session = Depends(get_session)):
    """List all simulations."""
    simulations = session.exec(select(Simulation)).all()
    return simulations


# ---------------------------------------------------------------------------
# Household simulation endpoints
# ---------------------------------------------------------------------------


@router.post("/household", response_model=HouseholdSimulationResponse)
def create_household_simulation(
    request: HouseholdSimulationRequest,
    session: Session = Depends(get_session),
):
    """Create a household simulation job.

    Creates a Simulation record for the given household and policy.
    Returns immediately with status "pending".
    Poll GET /simulations/household/{id} until status is "completed".
    """
    # Validate household exists
    household = session.get(Household, request.household_id)
    if not household:
        raise HTTPException(
            status_code=404,
            detail=f"Household {request.household_id} not found",
        )

    # Validate policy exists (if provided)
    if request.policy_id:
        policy = session.get(Policy, request.policy_id)
        if not policy:
            raise HTTPException(
                status_code=404,
                detail=f"Policy {request.policy_id} not found",
            )

    # Get model version
    model_version = _get_model_version(household.tax_benefit_model_name, session)

    # Get or create simulation (deterministic UUID)
    simulation = _get_or_create_simulation(
        simulation_type=SimulationType.HOUSEHOLD,
        model_version_id=model_version.id,
        policy_id=request.policy_id,
        dynamic_id=request.dynamic_id,
        session=session,
        household_id=request.household_id,
    )

    return _build_household_response(simulation)


@router.get("/household/{simulation_id}", response_model=HouseholdSimulationResponse)
def get_household_simulation(
    simulation_id: UUID,
    session: Session = Depends(get_session),
):
    """Get a household simulation's status and result."""
    simulation = session.get(Simulation, simulation_id)
    if not simulation:
        raise HTTPException(status_code=404, detail="Simulation not found")
    if simulation.simulation_type != SimulationType.HOUSEHOLD:
        raise HTTPException(
            status_code=400,
            detail="Simulation is not a household simulation",
        )

    return _build_household_response(simulation)


# ---------------------------------------------------------------------------
# Economy simulation endpoints
# ---------------------------------------------------------------------------


@router.post("/economy", response_model=EconomySimulationResponse)
def create_economy_simulation(
    request: EconomySimulationRequest,
    session: Session = Depends(get_session),
):
    """Create a single economy simulation.

    Creates a Simulation record for the given dataset/region and policy.
    Poll GET /simulations/economy/{id} until status is "completed".

    Note: standalone economy simulation computation will be connected
    in future tasks. For full baseline-vs-reform economy analysis,
    use POST /analysis/economic-impact instead.
    """
    # Resolve dataset and region
    dataset, region = _resolve_economy_dataset(
        request.tax_benefit_model_name,
        request.region,
        request.dataset_id,
        session,
        year=request.year,
    )

    # Validate policy exists (if provided)
    if request.policy_id:
        policy = session.get(Policy, request.policy_id)
        if not policy:
            raise HTTPException(
                status_code=404,
                detail=f"Policy {request.policy_id} not found",
            )

    # Extract filter parameters from region
    filter_field = region.filter_field if region and region.requires_filter else None
    filter_value = region.filter_value if region and region.requires_filter else None

    # Get model version
    model_version = _get_model_version(request.tax_benefit_model_name, session)

    # Get or create simulation (deterministic UUID)
    simulation = _get_or_create_simulation(
        simulation_type=SimulationType.ECONOMY,
        model_version_id=model_version.id,
        policy_id=request.policy_id,
        dynamic_id=request.dynamic_id,
        session=session,
        dataset_id=dataset.id,
        filter_field=filter_field,
        filter_value=filter_value,
        region_id=region.id if region else None,
        year=dataset.year,
    )

    return _build_economy_response(simulation, region)


@router.get("/economy/{simulation_id}", response_model=EconomySimulationResponse)
def get_economy_simulation(
    simulation_id: UUID,
    session: Session = Depends(get_session),
):
    """Get an economy simulation's status and result."""
    simulation = session.get(Simulation, simulation_id)
    if not simulation:
        raise HTTPException(status_code=404, detail="Simulation not found")
    if simulation.simulation_type != SimulationType.ECONOMY:
        raise HTTPException(
            status_code=400,
            detail="Simulation is not an economy simulation",
        )

    return _build_economy_response(simulation)


# ---------------------------------------------------------------------------
# Generic get (keep after specific routes to avoid path conflicts)
# ---------------------------------------------------------------------------


@router.get("/{simulation_id}", response_model=SimulationRead)
def get_simulation(simulation_id: UUID, session: Session = Depends(get_session)):
    """Get a specific simulation (any type)."""
    simulation = session.get(Simulation, simulation_id)
    if not simulation:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return simulation
