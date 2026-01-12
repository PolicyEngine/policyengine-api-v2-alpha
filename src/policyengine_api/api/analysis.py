"""Economic impact analysis endpoints.

Use these endpoints to analyse the economy-wide effects of policy reforms.
The /analysis/economic-impact endpoint compares baseline vs reform scenarios
across a population dataset, computing distributional impacts and program statistics.

This is an async operation - the endpoint returns immediately with a report_id,
and you poll /analysis/economic-impact/{report_id} until status is "completed".

WORKFLOW for full economic analysis:
1. Create a policy with parameter changes: POST /policies
2. Get a dataset: GET /datasets (look for UK/US datasets)
3. Start analysis: POST /analysis/economic-impact with policy_id and dataset_id
4. Check status: GET /analysis/economic-impact/{report_id} - repeat until status="completed"
5. Review results: The completed response includes decile_impacts and program_statistics
"""

import math
from typing import Literal
from uuid import UUID, uuid5

import logfire
from fastapi import APIRouter, Depends, HTTPException
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from pydantic import BaseModel, Field
from sqlmodel import Session, select

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
)
from policyengine_api.services.database import get_session
from policyengine_api.services.tax_benefit_models import get_latest_model_version


def get_traceparent() -> str | None:
    """Get the current W3C traceparent header for distributed tracing."""
    carrier: dict[str, str] = {}
    TraceContextTextMapPropagator().inject(carrier)
    return carrier.get("traceparent")


def _safe_float(value: float | None) -> float | None:
    """Convert NaN/inf to None for JSON serialization."""
    if value is None:
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return value


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
        default=None,
        description="Reform policy ID to compare against baseline (current law)",
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


def _download_dataset_local(filepath: str) -> str:
    """Download dataset from Supabase storage for local compute."""
    from pathlib import Path

    from policyengine_api.config import settings
    from supabase import create_client

    cache_dir = Path("/tmp/policyengine_dataset_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / filepath

    if cache_path.exists():
        return str(cache_path)

    client = create_client(settings.supabase_url, settings.supabase_service_key)
    data = client.storage.from_("datasets").download(filepath)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "wb") as f:
        f.write(data)

    return str(cache_path)


def _run_local_economy_comparison_uk(job_id: str, session: Session) -> None:
    """Run UK economy comparison analysis locally."""
    from datetime import datetime, timezone
    from uuid import UUID

    from policyengine.core import Simulation as PESimulation
    from policyengine.core.dynamic import Dynamic as PEDynamic
    from policyengine.core.policy import ParameterValue as PEParameterValue
    from policyengine.core.policy import Policy as PEPolicy
    from policyengine.outputs import DecileImpact as PEDecileImpact
    from policyengine.tax_benefit_models.uk import uk_latest
    from policyengine.tax_benefit_models.uk.datasets import PolicyEngineUKDataset
    from policyengine.tax_benefit_models.uk.outputs import (
        ProgrammeStatistics as PEProgrammeStats,
    )

    from policyengine_api.models import Policy as DBPolicy

    # Load report and simulations
    report = session.get(Report, UUID(job_id))
    if not report:
        raise ValueError(f"Report {job_id} not found")

    baseline_sim = session.get(Simulation, report.baseline_simulation_id)
    reform_sim = session.get(Simulation, report.reform_simulation_id)

    if not baseline_sim or not reform_sim:
        raise ValueError("Simulations not found")

    # Update status to running
    report.status = ReportStatus.RUNNING
    session.add(report)
    session.commit()

    # Get dataset
    dataset = session.get(Dataset, baseline_sim.dataset_id)
    if not dataset:
        raise ValueError(f"Dataset {baseline_sim.dataset_id} not found")

    pe_model_version = uk_latest
    param_lookup = {p.name: p for p in pe_model_version.parameters}

    def build_policy(policy_id):
        if not policy_id:
            return None
        db_policy = session.get(DBPolicy, policy_id)
        if not db_policy:
            return None
        pe_param_values = []
        for pv in db_policy.parameter_values:
            if not pv.parameter:
                continue
            pe_param = param_lookup.get(pv.parameter.name)
            if not pe_param:
                continue
            pe_pv = PEParameterValue(
                parameter=pe_param,
                value=pv.value_json.get("value")
                if isinstance(pv.value_json, dict)
                else pv.value_json,
                start_date=pv.start_date,
                end_date=pv.end_date,
            )
            pe_param_values.append(pe_pv)
        return PEPolicy(
            name=db_policy.name,
            description=db_policy.description,
            parameter_values=pe_param_values,
        )

    def build_dynamic(dynamic_id):
        if not dynamic_id:
            return None
        from policyengine_api.models import Dynamic as DBDynamic

        db_dynamic = session.get(DBDynamic, dynamic_id)
        if not db_dynamic:
            return None
        pe_param_values = []
        for pv in db_dynamic.parameter_values:
            if not pv.parameter:
                continue
            pe_param = param_lookup.get(pv.parameter.name)
            if not pe_param:
                continue
            pe_pv = PEParameterValue(
                parameter=pe_param,
                value=pv.value_json.get("value")
                if isinstance(pv.value_json, dict)
                else pv.value_json,
                start_date=pv.start_date,
                end_date=pv.end_date,
            )
            pe_param_values.append(pe_pv)
        return PEDynamic(
            name=db_dynamic.name,
            description=db_dynamic.description,
            parameter_values=pe_param_values,
        )

    baseline_policy = build_policy(baseline_sim.policy_id)
    reform_policy = build_policy(reform_sim.policy_id)
    baseline_dynamic = build_dynamic(baseline_sim.dynamic_id)
    reform_dynamic = build_dynamic(reform_sim.dynamic_id)

    # Download dataset
    local_path = _download_dataset_local(dataset.filepath)
    pe_dataset = PolicyEngineUKDataset(
        name=dataset.name,
        description=dataset.description or "",
        filepath=local_path,
        year=dataset.year,
    )

    # Run simulations
    pe_baseline_sim = PESimulation(
        dataset=pe_dataset,
        tax_benefit_model_version=pe_model_version,
        policy=baseline_policy,
        dynamic=baseline_dynamic,
    )
    pe_baseline_sim.ensure()

    pe_reform_sim = PESimulation(
        dataset=pe_dataset,
        tax_benefit_model_version=pe_model_version,
        policy=reform_policy,
        dynamic=reform_dynamic,
    )
    pe_reform_sim.ensure()

    # Calculate decile impacts
    for decile_num in range(1, 11):
        di = PEDecileImpact(
            baseline_simulation=pe_baseline_sim,
            reform_simulation=pe_reform_sim,
            decile=decile_num,
        )
        di.run()
        decile_impact = DecileImpact(
            baseline_simulation_id=baseline_sim.id,
            reform_simulation_id=reform_sim.id,
            report_id=report.id,
            income_variable=di.income_variable,
            entity=di.entity,
            decile=di.decile,
            quantiles=di.quantiles,
            baseline_mean=di.baseline_mean,
            reform_mean=di.reform_mean,
            absolute_change=di.absolute_change,
            relative_change=di.relative_change,
            count_better_off=di.count_better_off,
            count_worse_off=di.count_worse_off,
            count_no_change=di.count_no_change,
        )
        session.add(decile_impact)

    # Calculate program statistics
    PEProgrammeStats.model_rebuild(_types_namespace={"Simulation": PESimulation})
    programmes = {
        "income_tax": {"entity": "person", "is_tax": True},
        "national_insurance": {"entity": "person", "is_tax": True},
        "universal_credit": {"entity": "person", "is_tax": False},
        "child_benefit": {"entity": "person", "is_tax": False},
    }
    for prog_name, prog_info in programmes.items():
        try:
            ps = PEProgrammeStats(
                baseline_simulation=pe_baseline_sim,
                reform_simulation=pe_reform_sim,
                programme_name=prog_name,
                entity=prog_info["entity"],
                is_tax=prog_info["is_tax"],
            )
            ps.run()
            program_stat = ProgramStatistics(
                baseline_simulation_id=baseline_sim.id,
                reform_simulation_id=reform_sim.id,
                report_id=report.id,
                program_name=prog_name,
                entity=prog_info["entity"],
                is_tax=prog_info["is_tax"],
                baseline_total=ps.baseline_total,
                reform_total=ps.reform_total,
                change=ps.change,
                baseline_count=ps.baseline_count,
                reform_count=ps.reform_count,
                winners=ps.winners,
                losers=ps.losers,
            )
            session.add(program_stat)
        except KeyError:
            pass  # Variable not found in model

    # Mark completed
    baseline_sim.status = SimulationStatus.COMPLETED
    baseline_sim.completed_at = datetime.now(timezone.utc)
    reform_sim.status = SimulationStatus.COMPLETED
    reform_sim.completed_at = datetime.now(timezone.utc)
    report.status = ReportStatus.COMPLETED
    session.add(baseline_sim)
    session.add(reform_sim)
    session.add(report)
    session.commit()


def _trigger_economy_comparison(
    job_id: str, tax_benefit_model_name: str, session: Session | None = None
) -> None:
    """Trigger economy comparison analysis (local or Modal)."""
    from policyengine_api.config import settings

    traceparent = get_traceparent()

    if not settings.agent_use_modal and session is not None:
        # Run locally
        if tax_benefit_model_name == "policyengine_uk":
            _run_local_economy_comparison_uk(job_id, session)
        else:
            # US not implemented for local yet - fall back to Modal
            import modal

            fn = modal.Function.from_name("policyengine", "economy_comparison_us")
            fn.spawn(job_id=job_id, traceparent=traceparent)
    else:
        # Use Modal
        import modal

        if tax_benefit_model_name == "policyengine_uk":
            fn = modal.Function.from_name("policyengine", "economy_comparison_uk")
        else:
            fn = modal.Function.from_name("policyengine", "economy_comparison_us")

        fn.spawn(job_id=job_id, traceparent=traceparent)


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
    model_version = get_latest_model_version(request.tax_benefit_model_name, session)

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

    # Trigger computation if report is pending
    if report.status == ReportStatus.PENDING:
        with logfire.span("trigger_economy_comparison", job_id=str(report.id)):
            _trigger_economy_comparison(
                str(report.id), request.tax_benefit_model_name, session
            )

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
