"""Economic impact analysis endpoints.

Use these endpoints to analyse the economy-wide effects of policy reforms.
The /analysis/economic-impact endpoint compares baseline vs reform scenarios
across a population dataset, computing distributional impacts and program statistics.

This is an async operation - the endpoint returns immediately with a report_id,
and you poll /analysis/economic-impact/{report_id} until status is "completed".
"""

import math
from typing import Literal
from uuid import UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select


def _safe_float(value: float | None) -> float | None:
    """Convert NaN/inf to None for JSON serialization."""
    if value is None:
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return value

from policyengine_api.models import (
    Dataset,
    DecileImpact,
    DecileImpactRead,
    ProgramStatistics,
    ProgramStatisticsRead,
    Report,
    ReportStatus,
    Simulation,
    SimulationStatus,
    TaxBenefitModel,
    TaxBenefitModelVersion,
)
from policyengine_api.services.database import get_session

# Namespace for deterministic UUIDs
SIMULATION_NAMESPACE = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
REPORT_NAMESPACE = UUID("b2c3d4e5-f6a7-8901-bcde-f12345678901")

router = APIRouter(prefix="/analysis", tags=["analysis"])


class EconomicImpactRequest(BaseModel):
    """Request body for economic impact analysis.

    Example:
    {
        "tax_benefit_model_name": "policyengine_uk",
        "dataset_id": "uuid-from-datasets-endpoint",
        "policy_id": "uuid-of-reform-policy"
    }
    """

    tax_benefit_model_name: Literal["policyengine_uk", "policyengine_us"] = Field(
        description="Which country model to use"
    )
    dataset_id: UUID = Field(
        description="Dataset ID from /datasets endpoint containing population microdata"
    )
    policy_id: UUID | None = Field(
        default=None, description="Reform policy ID to compare against baseline (current law)"
    )
    dynamic_id: UUID | None = Field(
        default=None, description="Optional behavioural response specification ID"
    )


class SimulationInfo(BaseModel):
    """Simulation status info."""

    id: UUID
    status: SimulationStatus
    error_message: str | None = None


class EconomicImpactResponse(BaseModel):
    """Response from economic impact analysis."""

    report_id: UUID
    status: ReportStatus
    baseline_simulation: SimulationInfo
    reform_simulation: SimulationInfo
    error_message: str | None = None
    decile_impacts: list[DecileImpactRead] | None = None
    program_statistics: list[ProgramStatisticsRead] | None = None


def _get_model_version(
    tax_benefit_model_name: str, session: Session
) -> TaxBenefitModelVersion:
    """Get the latest tax benefit model version."""
    model_name = tax_benefit_model_name.replace("_", "-")

    model = session.exec(
        select(TaxBenefitModel).where(TaxBenefitModel.name == model_name)
    ).first()
    if not model:
        raise HTTPException(
            status_code=404, detail=f"Tax benefit model {model_name} not found"
        )

    version = session.exec(
        select(TaxBenefitModelVersion)
        .where(TaxBenefitModelVersion.model_id == model.id)
        .order_by(TaxBenefitModelVersion.created_at.desc())
    ).first()
    if not version:
        raise HTTPException(
            status_code=404, detail=f"No version found for model {model_name}"
        )

    return version


def _get_deterministic_simulation_id(
    dataset_id: UUID,
    model_version_id: UUID,
    policy_id: UUID | None,
    dynamic_id: UUID | None,
) -> UUID:
    """Generate a deterministic UUID from simulation parameters."""
    key = f"{dataset_id}:{model_version_id}:{policy_id}:{dynamic_id}"
    return uuid5(SIMULATION_NAMESPACE, key)


def _get_deterministic_report_id(
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
) -> UUID:
    """Generate a deterministic UUID from report parameters."""
    key = f"{baseline_sim_id}:{reform_sim_id}"
    return uuid5(REPORT_NAMESPACE, key)


def _get_or_create_simulation(
    dataset_id: UUID,
    model_version_id: UUID,
    policy_id: UUID | None,
    dynamic_id: UUID | None,
    session: Session,
) -> Simulation:
    """Get existing simulation or create a new one."""
    sim_id = _get_deterministic_simulation_id(
        dataset_id, model_version_id, policy_id, dynamic_id
    )

    existing = session.get(Simulation, sim_id)
    if existing:
        return existing

    simulation = Simulation(
        id=sim_id,
        dataset_id=dataset_id,
        tax_benefit_model_version_id=model_version_id,
        policy_id=policy_id,
        dynamic_id=dynamic_id,
        status=SimulationStatus.PENDING,
    )
    session.add(simulation)
    session.commit()
    session.refresh(simulation)
    return simulation


def _get_or_create_report(
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    label: str,
    session: Session,
) -> Report:
    """Get existing report or create a new one."""
    report_id = _get_deterministic_report_id(baseline_sim_id, reform_sim_id)

    existing = session.get(Report, report_id)
    if existing:
        return existing

    report = Report(
        id=report_id,
        label=label,
        baseline_simulation_id=baseline_sim_id,
        reform_simulation_id=reform_sim_id,
        status=ReportStatus.PENDING,
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return report


def _build_response(
    report: Report,
    baseline_sim: Simulation,
    reform_sim: Simulation,
    session: Session,
) -> EconomicImpactResponse:
    """Build response from report and simulations."""
    decile_impacts = None
    program_statistics = None

    if report.status == ReportStatus.COMPLETED:
        # Fetch decile impacts for this report
        deciles = session.exec(
            select(DecileImpact).where(DecileImpact.report_id == report.id)
        ).all()
        decile_impacts = [
            DecileImpactRead(
                id=d.id,
                created_at=d.created_at,
                baseline_simulation_id=d.baseline_simulation_id,
                reform_simulation_id=d.reform_simulation_id,
                report_id=d.report_id,
                income_variable=d.income_variable,
                entity=d.entity,
                decile=d.decile,
                quantiles=d.quantiles,
                baseline_mean=_safe_float(d.baseline_mean),
                reform_mean=_safe_float(d.reform_mean),
                absolute_change=_safe_float(d.absolute_change),
                relative_change=_safe_float(d.relative_change),
                count_better_off=_safe_float(d.count_better_off),
                count_worse_off=_safe_float(d.count_worse_off),
                count_no_change=_safe_float(d.count_no_change),
            )
            for d in deciles
        ]

        # Fetch program statistics for this report
        stats = session.exec(
            select(ProgramStatistics).where(ProgramStatistics.report_id == report.id)
        ).all()
        program_statistics = [
            ProgramStatisticsRead(
                id=s.id,
                created_at=s.created_at,
                baseline_simulation_id=s.baseline_simulation_id,
                reform_simulation_id=s.reform_simulation_id,
                report_id=s.report_id,
                program_name=s.program_name,
                entity=s.entity,
                is_tax=s.is_tax,
                baseline_total=_safe_float(s.baseline_total),
                reform_total=_safe_float(s.reform_total),
                change=_safe_float(s.change),
                baseline_count=_safe_float(s.baseline_count),
                reform_count=_safe_float(s.reform_count),
                winners=_safe_float(s.winners),
                losers=_safe_float(s.losers),
            )
            for s in stats
        ]

    return EconomicImpactResponse(
        report_id=report.id,
        status=report.status,
        baseline_simulation=SimulationInfo(
            id=baseline_sim.id,
            status=baseline_sim.status,
            error_message=baseline_sim.error_message,
        ),
        reform_simulation=SimulationInfo(
            id=reform_sim.id,
            status=reform_sim.status,
            error_message=reform_sim.error_message,
        ),
        error_message=report.error_message,
        decile_impacts=decile_impacts,
        program_statistics=program_statistics,
    )


@router.post("/economic-impact", response_model=EconomicImpactResponse)
def economic_impact(
    request: EconomicImpactRequest,
    session: Session = Depends(get_session),
) -> EconomicImpactResponse:
    """Run economy-wide impact analysis comparing baseline vs reform.

    This is an async operation. The endpoint returns immediately with a report_id
    and status="pending". Poll GET /analysis/economic-impact/{report_id} until
    status="completed" to get results.

    Results include decile impacts (income changes by income group) and
    program statistics (budgetary effects of tax/benefit programs).
    """
    # Validate dataset exists
    dataset = session.get(Dataset, request.dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=404, detail=f"Dataset {request.dataset_id} not found"
        )

    # Get model version
    model_version = _get_model_version(request.tax_benefit_model_name, session)

    # Get or create simulations
    baseline_sim = _get_or_create_simulation(
        dataset_id=request.dataset_id,
        model_version_id=model_version.id,
        policy_id=None,
        dynamic_id=request.dynamic_id,
        session=session,
    )

    reform_sim = _get_or_create_simulation(
        dataset_id=request.dataset_id,
        model_version_id=model_version.id,
        policy_id=request.policy_id,
        dynamic_id=request.dynamic_id,
        session=session,
    )

    # Get or create report
    label = f"Economic impact: {request.tax_benefit_model_name}"
    if request.policy_id:
        label += f" (policy {request.policy_id})"

    report = _get_or_create_report(baseline_sim.id, reform_sim.id, label, session)

    return _build_response(report, baseline_sim, reform_sim, session)


@router.get("/economic-impact/{report_id}", response_model=EconomicImpactResponse)
def get_economic_impact_status(
    report_id: UUID,
    session: Session = Depends(get_session),
) -> EconomicImpactResponse:
    """Get status and results of economic impact analysis."""
    report = session.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

    if not report.baseline_simulation_id or not report.reform_simulation_id:
        raise HTTPException(status_code=500, detail="Report missing simulation IDs")

    baseline_sim = session.get(Simulation, report.baseline_simulation_id)
    reform_sim = session.get(Simulation, report.reform_simulation_id)

    if not baseline_sim or not reform_sim:
        raise HTTPException(status_code=500, detail="Simulation data missing")

    return _build_response(report, baseline_sim, reform_sim, session)
