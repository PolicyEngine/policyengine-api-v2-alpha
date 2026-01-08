"""Agent result upload endpoints.

These endpoints allow the AI agent to directly write simulation results,
enabling it to run custom computations and store the outputs.
"""

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

import modal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from policyengine_api.models import (
    DecileImpact,
    HouseholdJob,
    HouseholdJobStatus,
    Inequality,
    Policy,
    Poverty,
    ProgramStatistics,
    Report,
    ReportStatus,
    Simulation,
    SimulationStatus,
    TaxBenefitModel,
    TaxBenefitModelVersion,
    Dataset,
)
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/agent/results", tags=["agent-results"])

# Also create a router without the /results prefix for structural reform trigger
agent_router = APIRouter(prefix="/agent", tags=["agent"])


# Request schemas


class SimulationResultUpload(BaseModel):
    """Upload completed simulation result."""

    simulation_id: UUID
    status: Literal["completed", "failed"] = "completed"
    error_message: str | None = None


class HouseholdResultUpload(BaseModel):
    """Upload completed household calculation result."""

    job_id: UUID
    status: Literal["completed", "failed"] = "completed"
    result: dict | None = None
    error_message: str | None = None


class DecileImpactUpload(BaseModel):
    """Upload decile impact data."""

    baseline_simulation_id: UUID
    reform_simulation_id: UUID
    report_id: UUID
    income_variable: str = "household_net_income"
    entity: str = "household"
    decile: int = Field(ge=1, le=10)
    quantiles: int = 10
    baseline_mean: float
    reform_mean: float
    absolute_change: float
    relative_change: float
    count_better_off: float = 0
    count_worse_off: float = 0
    count_no_change: float = 0


class ProgramStatisticsUpload(BaseModel):
    """Upload program statistics data."""

    baseline_simulation_id: UUID
    reform_simulation_id: UUID
    report_id: UUID
    program_name: str
    entity: str
    is_tax: bool
    baseline_total: float
    reform_total: float
    change: float
    baseline_count: float = 0
    reform_count: float = 0
    winners: float = 0
    losers: float = 0


class PovertyUpload(BaseModel):
    """Upload poverty rate data."""

    simulation_id: UUID
    report_id: UUID
    poverty_type: str
    entity: str
    filter_variable: str | None = None
    headcount: float
    total_population: float
    rate: float


class InequalityUpload(BaseModel):
    """Upload inequality metrics."""

    simulation_id: UUID
    report_id: UUID
    income_variable: str = "household_net_income"
    entity: str = "household"
    gini: float
    top_10_share: float
    top_1_share: float
    bottom_50_share: float


class ReportStatusUpdate(BaseModel):
    """Update report status."""

    report_id: UUID
    status: Literal["pending", "running", "completed", "failed"]
    error_message: str | None = None


class PolicyWithModifierCreate(BaseModel):
    """Create a policy with optional simulation modifier.

    The simulation_modifier is Python code that defines custom variable
    formulas for structural reforms. It should define a `modify(simulation)`
    function that modifies the simulation's tax-benefit system.

    Example:
    ```python
    def modify(simulation):
        from policyengine_core.variables import Variable

        @simulation.tax_benefit_system.variable("my_new_benefit")
        class my_new_benefit(Variable):
            value_type = float
            entity = Person
            definition_period = YEAR

            def formula(person, period, parameters):
                income = person("employment_income", period)
                return where(income < 20000, 1000, 0)
    ```
    """

    name: str
    description: str | None = None
    simulation_modifier: str | None = None
    parameter_values: list[dict] = []


# Endpoints


@router.post("/simulation")
def upload_simulation_result(
    data: SimulationResultUpload,
    session: Session = Depends(get_session),
) -> dict:
    """Mark a simulation as completed or failed."""
    simulation = session.get(Simulation, data.simulation_id)
    if not simulation:
        raise HTTPException(
            status_code=404, detail=f"Simulation {data.simulation_id} not found"
        )

    if data.status == "completed":
        simulation.status = SimulationStatus.COMPLETED
        simulation.completed_at = datetime.now(timezone.utc)
    else:
        simulation.status = SimulationStatus.FAILED
        simulation.error_message = data.error_message

    session.add(simulation)
    session.commit()

    return {"status": "ok", "simulation_id": str(simulation.id)}


@router.post("/household")
def upload_household_result(
    data: HouseholdResultUpload,
    session: Session = Depends(get_session),
) -> dict:
    """Upload completed household calculation result."""
    job = session.get(HouseholdJob, data.job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {data.job_id} not found")

    if data.status == "completed":
        job.status = HouseholdJobStatus.COMPLETED
        job.result = data.result
        job.completed_at = datetime.now(timezone.utc)
    else:
        job.status = HouseholdJobStatus.FAILED
        job.error_message = data.error_message
        job.completed_at = datetime.now(timezone.utc)

    session.add(job)
    session.commit()

    return {"status": "ok", "job_id": str(job.id)}


@router.post("/decile-impact")
def upload_decile_impact(
    data: DecileImpactUpload,
    session: Session = Depends(get_session),
) -> dict:
    """Upload decile impact data for a report."""
    # Verify report exists
    report = session.get(Report, data.report_id)
    if not report:
        raise HTTPException(
            status_code=404, detail=f"Report {data.report_id} not found"
        )

    decile_impact = DecileImpact(
        baseline_simulation_id=data.baseline_simulation_id,
        reform_simulation_id=data.reform_simulation_id,
        report_id=data.report_id,
        income_variable=data.income_variable,
        entity=data.entity,
        decile=data.decile,
        quantiles=data.quantiles,
        baseline_mean=data.baseline_mean,
        reform_mean=data.reform_mean,
        absolute_change=data.absolute_change,
        relative_change=data.relative_change,
        count_better_off=data.count_better_off,
        count_worse_off=data.count_worse_off,
        count_no_change=data.count_no_change,
    )
    session.add(decile_impact)
    session.commit()
    session.refresh(decile_impact)

    return {"status": "ok", "decile_impact_id": str(decile_impact.id)}


@router.post("/program-statistics")
def upload_program_statistics(
    data: ProgramStatisticsUpload,
    session: Session = Depends(get_session),
) -> dict:
    """Upload program statistics data for a report."""
    # Verify report exists
    report = session.get(Report, data.report_id)
    if not report:
        raise HTTPException(
            status_code=404, detail=f"Report {data.report_id} not found"
        )

    program_stat = ProgramStatistics(
        baseline_simulation_id=data.baseline_simulation_id,
        reform_simulation_id=data.reform_simulation_id,
        report_id=data.report_id,
        program_name=data.program_name,
        entity=data.entity,
        is_tax=data.is_tax,
        baseline_total=data.baseline_total,
        reform_total=data.reform_total,
        change=data.change,
        baseline_count=data.baseline_count,
        reform_count=data.reform_count,
        winners=data.winners,
        losers=data.losers,
    )
    session.add(program_stat)
    session.commit()
    session.refresh(program_stat)

    return {"status": "ok", "program_statistics_id": str(program_stat.id)}


@router.post("/poverty")
def upload_poverty(
    data: PovertyUpload,
    session: Session = Depends(get_session),
) -> dict:
    """Upload poverty rate data."""
    poverty = Poverty(
        simulation_id=data.simulation_id,
        report_id=data.report_id,
        poverty_type=data.poverty_type,
        entity=data.entity,
        filter_variable=data.filter_variable,
        headcount=data.headcount,
        total_population=data.total_population,
        rate=data.rate,
    )
    session.add(poverty)
    session.commit()
    session.refresh(poverty)

    return {"status": "ok", "poverty_id": str(poverty.id)}


@router.post("/inequality")
def upload_inequality(
    data: InequalityUpload,
    session: Session = Depends(get_session),
) -> dict:
    """Upload inequality metrics."""
    inequality = Inequality(
        simulation_id=data.simulation_id,
        report_id=data.report_id,
        income_variable=data.income_variable,
        entity=data.entity,
        gini=data.gini,
        top_10_share=data.top_10_share,
        top_1_share=data.top_1_share,
        bottom_50_share=data.bottom_50_share,
    )
    session.add(inequality)
    session.commit()
    session.refresh(inequality)

    return {"status": "ok", "inequality_id": str(inequality.id)}


@router.post("/report-status")
def update_report_status(
    data: ReportStatusUpdate,
    session: Session = Depends(get_session),
) -> dict:
    """Update report status."""
    report = session.get(Report, data.report_id)
    if not report:
        raise HTTPException(
            status_code=404, detail=f"Report {data.report_id} not found"
        )

    status_map = {
        "pending": ReportStatus.PENDING,
        "running": ReportStatus.RUNNING,
        "completed": ReportStatus.COMPLETED,
        "failed": ReportStatus.FAILED,
    }
    report.status = status_map[data.status]
    if data.error_message:
        report.error_message = data.error_message

    session.add(report)
    session.commit()

    return {"status": "ok", "report_id": str(report.id)}


@router.post("/policy-with-modifier")
def create_policy_with_modifier(
    data: PolicyWithModifierCreate,
    session: Session = Depends(get_session),
) -> dict:
    """Create a policy with an optional simulation modifier.

    This endpoint allows the agent to create policies that include
    structural reforms via Python code in the simulation_modifier field.
    """
    policy = Policy(
        name=data.name,
        description=data.description,
        simulation_modifier=data.simulation_modifier,
    )
    session.add(policy)
    session.commit()
    session.refresh(policy)

    # Add parameter values if provided
    if data.parameter_values:
        from policyengine_api.models import ParameterValue

        for pv_data in data.parameter_values:
            pv = ParameterValue(
                policy_id=policy.id,
                parameter_id=pv_data.get("parameter_id"),
                value_json=pv_data.get("value_json"),
                start_date=pv_data.get("start_date"),
                end_date=pv_data.get("end_date"),
            )
            session.add(pv)
        session.commit()

    return {
        "status": "ok",
        "policy_id": str(policy.id),
        "name": policy.name,
        "has_modifier": policy.simulation_modifier is not None,
    }


# Structural reform trigger endpoint


class StructuralReformRequest(BaseModel):
    """Request to run a structural reform analysis."""

    policy_id: str
    dataset_id: str
    country: Literal["uk", "us"]


@agent_router.post("/run-structural-reform")
def run_structural_reform(
    data: StructuralReformRequest,
    session: Session = Depends(get_session),
) -> dict:
    """Trigger a structural reform analysis.

    This creates the necessary simulation and report records, then triggers
    the appropriate Modal function to run the analysis with the simulation_modifier.
    """
    from uuid import UUID as UUIDType

    # Verify policy exists and has a modifier
    policy = session.get(Policy, UUIDType(data.policy_id))
    if not policy:
        raise HTTPException(
            status_code=404, detail=f"Policy {data.policy_id} not found"
        )

    if not policy.simulation_modifier:
        raise HTTPException(
            status_code=400,
            detail="Policy has no simulation_modifier. Use /analysis/economic-impact instead.",
        )

    # Verify dataset exists
    dataset = session.get(Dataset, UUIDType(data.dataset_id))
    if not dataset:
        raise HTTPException(
            status_code=404, detail=f"Dataset {data.dataset_id} not found"
        )

    # Get model version
    tax_benefit_model_name = (
        "policyengine-uk" if data.country == "uk" else "policyengine-us"
    )
    from sqlmodel import select

    # First find the model by name, then get its latest version
    stmt = select(TaxBenefitModel).where(TaxBenefitModel.name == tax_benefit_model_name)
    model = session.exec(stmt).first()
    if not model:
        raise HTTPException(
            status_code=404,
            detail=f"No model found for {tax_benefit_model_name}",
        )

    stmt = select(TaxBenefitModelVersion).where(
        TaxBenefitModelVersion.model_id == model.id
    )
    model_version = session.exec(stmt).first()
    if not model_version:
        raise HTTPException(
            status_code=404,
            detail=f"No model version found for {tax_benefit_model_name}",
        )

    # Create baseline policy
    baseline_policy = Policy(
        name="Baseline (current law)",
        description="Auto-generated baseline for structural reform comparison",
    )
    session.add(baseline_policy)
    session.commit()
    session.refresh(baseline_policy)

    # Create baseline simulation
    baseline_sim = Simulation(
        dataset_id=dataset.id,
        tax_benefit_model_version_id=model_version.id,
        policy_id=baseline_policy.id,
        status=SimulationStatus.PENDING,
    )
    session.add(baseline_sim)

    # Create reform simulation
    reform_sim = Simulation(
        dataset_id=dataset.id,
        tax_benefit_model_version_id=model_version.id,
        policy_id=policy.id,
        status=SimulationStatus.PENDING,
    )
    session.add(reform_sim)
    session.commit()
    session.refresh(baseline_sim)
    session.refresh(reform_sim)

    # Create report
    report = Report(
        baseline_simulation_id=baseline_sim.id,
        reform_simulation_id=reform_sim.id,
        status=ReportStatus.PENDING,
    )
    session.add(report)
    session.commit()
    session.refresh(report)

    # Trigger the appropriate Modal function
    try:
        if data.country == "uk":
            from policyengine_api.modal_app import economy_comparison_uk

            economy_comparison_uk.spawn(job_id=str(report.id))
        else:
            from policyengine_api.modal_app import economy_comparison_us

            economy_comparison_us.spawn(job_id=str(report.id))
    except Exception as e:
        # Mark as failed if Modal trigger fails
        report.status = ReportStatus.FAILED
        report.error_message = f"Failed to trigger Modal: {str(e)}"
        session.add(report)
        session.commit()
        raise HTTPException(
            status_code=500, detail=f"Failed to trigger Modal: {str(e)}"
        )

    return {
        "status": "ok",
        "report_id": str(report.id),
        "baseline_simulation_id": str(baseline_sim.id),
        "reform_simulation_id": str(reform_sim.id),
        "message": "Structural reform analysis triggered. Poll /analysis/economic-impact/{report_id} for results.",
    }
