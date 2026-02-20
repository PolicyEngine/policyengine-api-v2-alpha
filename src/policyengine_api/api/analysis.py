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
    BudgetSummary,
    BudgetSummaryRead,
    Dataset,
    DecileImpact,
    DecileImpactRead,
    Inequality,
    InequalityRead,
    IntraDecileImpact,
    IntraDecileImpactRead,
    Poverty,
    PovertyRead,
    ProgramStatistics,
    ProgramStatisticsRead,
    Region,
    Report,
    ReportStatus,
    Simulation,
    SimulationStatus,
    SimulationType,
    TaxBenefitModel,
    TaxBenefitModelVersion,
)
from policyengine_api.services.database import get_session


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

    Example with dataset_id:
    {
        "tax_benefit_model_name": "policyengine_uk",
        "dataset_id": "uuid-from-datasets-endpoint",
        "policy_id": "uuid-of-reform-policy"
    }

    Example with region:
    {
        "tax_benefit_model_name": "policyengine_us",
        "region": "state/ca",
        "policy_id": "uuid-of-reform-policy"
    }
    """

    tax_benefit_model_name: Literal["policyengine_uk", "policyengine_us"] = Field(
        description="Which country model to use"
    )
    dataset_id: UUID | None = Field(
        default=None,
        description="Dataset ID from /datasets endpoint. Either dataset_id or region must be provided.",
    )
    region: str | None = Field(
        default=None,
        description="Region code (e.g., 'state/ca', 'us'). Either dataset_id or region must be provided.",
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


class RegionInfo(BaseModel):
    """Region information used in analysis."""

    code: str
    label: str
    region_type: str
    requires_filter: bool
    filter_field: str | None = None
    filter_value: str | None = None


class EconomicImpactResponse(BaseModel):
    """Response from economic impact analysis."""

    report_id: UUID
    status: ReportStatus
    baseline_simulation: SimulationInfo
    reform_simulation: SimulationInfo
    region: RegionInfo | None = None
    error_message: str | None = None
    decile_impacts: list[DecileImpactRead] | None = None
    program_statistics: list[ProgramStatisticsRead] | None = None
    poverty: list[PovertyRead] | None = None
    inequality: list[InequalityRead] | None = None
    budget_summary: list[BudgetSummaryRead] | None = None
    intra_decile: list[IntraDecileImpactRead] | None = None
    detailed_budget: dict[str, dict[str, float | None]] | None = None


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
    simulation_type: SimulationType,
    model_version_id: UUID,
    policy_id: UUID | None,
    dynamic_id: UUID | None,
    dataset_id: UUID | None = None,
    household_id: UUID | None = None,
    filter_field: str | None = None,
    filter_value: str | None = None,
) -> UUID:
    """Generate a deterministic UUID from simulation parameters."""
    if simulation_type == SimulationType.ECONOMY:
        key = f"economy:{dataset_id}:{model_version_id}:{policy_id}:{dynamic_id}:{filter_field}:{filter_value}"
    else:
        key = f"household:{household_id}:{model_version_id}:{policy_id}:{dynamic_id}"
    return uuid5(SIMULATION_NAMESPACE, key)


def _get_deterministic_report_id(
    baseline_sim_id: UUID,
    reform_sim_id: UUID | None,
) -> UUID:
    """Generate a deterministic UUID from report parameters."""
    key = f"{baseline_sim_id}:{reform_sim_id}"
    return uuid5(REPORT_NAMESPACE, key)


def _get_or_create_simulation(
    simulation_type: SimulationType,
    model_version_id: UUID,
    policy_id: UUID | None,
    dynamic_id: UUID | None,
    session: Session,
    dataset_id: UUID | None = None,
    household_id: UUID | None = None,
    filter_field: str | None = None,
    filter_value: str | None = None,
) -> Simulation:
    """Get existing simulation or create a new one."""
    sim_id = _get_deterministic_simulation_id(
        simulation_type,
        model_version_id,
        policy_id,
        dynamic_id,
        dataset_id=dataset_id,
        household_id=household_id,
        filter_field=filter_field,
        filter_value=filter_value,
    )

    existing = session.get(Simulation, sim_id)
    if existing:
        return existing

    simulation = Simulation(
        id=sim_id,
        simulation_type=simulation_type,
        dataset_id=dataset_id,
        household_id=household_id,
        tax_benefit_model_version_id=model_version_id,
        policy_id=policy_id,
        dynamic_id=dynamic_id,
        status=SimulationStatus.PENDING,
        filter_field=filter_field,
        filter_value=filter_value,
    )
    session.add(simulation)
    session.commit()
    session.refresh(simulation)
    return simulation


def _get_or_create_report(
    baseline_sim_id: UUID,
    reform_sim_id: UUID | None,
    label: str,
    report_type: str,
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
        report_type=report_type,
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
    region: Region | None = None,
) -> EconomicImpactResponse:
    """Build response from report and simulations."""
    decile_impacts = None
    program_statistics = None
    poverty_records = None
    inequality_records = None
    budget_summary_records = None
    intra_decile_records = None
    detailed_budget = None

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

        # Build detailed_budget: V1-compatible per-program breakdown
        # keyed by program name with baseline/reform/difference values.
        detailed_budget = {
            s.program_name: {
                "baseline": _safe_float(s.baseline_total),
                "reform": _safe_float(s.reform_total),
                "difference": _safe_float(s.change),
            }
            for s in stats
        }

        # Fetch poverty records for this report
        pov_rows = session.exec(
            select(Poverty).where(Poverty.report_id == report.id)
        ).all()
        poverty_records = [
            PovertyRead(
                id=p.id,
                created_at=p.created_at,
                simulation_id=p.simulation_id,
                report_id=p.report_id,
                poverty_type=p.poverty_type,
                entity=p.entity,
                filter_variable=p.filter_variable,
                headcount=_safe_float(p.headcount),
                total_population=_safe_float(p.total_population),
                rate=_safe_float(p.rate),
            )
            for p in pov_rows
        ]

        # Fetch inequality records for this report
        ineq_rows = session.exec(
            select(Inequality).where(Inequality.report_id == report.id)
        ).all()
        inequality_records = [
            InequalityRead(
                id=i.id,
                created_at=i.created_at,
                simulation_id=i.simulation_id,
                report_id=i.report_id,
                income_variable=i.income_variable,
                entity=i.entity,
                gini=_safe_float(i.gini),
                top_10_share=_safe_float(i.top_10_share),
                top_1_share=_safe_float(i.top_1_share),
                bottom_50_share=_safe_float(i.bottom_50_share),
            )
            for i in ineq_rows
        ]

        # Fetch budget summary records for this report
        budget_rows = session.exec(
            select(BudgetSummary).where(BudgetSummary.report_id == report.id)
        ).all()
        budget_summary_records = [
            BudgetSummaryRead(
                id=b.id,
                created_at=b.created_at,
                baseline_simulation_id=b.baseline_simulation_id,
                reform_simulation_id=b.reform_simulation_id,
                report_id=b.report_id,
                variable_name=b.variable_name,
                entity=b.entity,
                baseline_total=_safe_float(b.baseline_total),
                reform_total=_safe_float(b.reform_total),
                change=_safe_float(b.change),
            )
            for b in budget_rows
        ]

        # Fetch intra-decile impact records for this report
        intra_rows = session.exec(
            select(IntraDecileImpact).where(
                IntraDecileImpact.report_id == report.id
            )
        ).all()
        intra_decile_records = [
            IntraDecileImpactRead(
                id=r.id,
                created_at=r.created_at,
                baseline_simulation_id=r.baseline_simulation_id,
                reform_simulation_id=r.reform_simulation_id,
                report_id=r.report_id,
                decile=r.decile,
                lose_more_than_5pct=_safe_float(r.lose_more_than_5pct),
                lose_less_than_5pct=_safe_float(r.lose_less_than_5pct),
                no_change=_safe_float(r.no_change),
                gain_less_than_5pct=_safe_float(r.gain_less_than_5pct),
                gain_more_than_5pct=_safe_float(r.gain_more_than_5pct),
            )
            for r in intra_rows
        ]

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
        region=region_info,
        error_message=report.error_message,
        decile_impacts=decile_impacts,
        program_statistics=program_statistics,
        poverty=poverty_records,
        inequality=inequality_records,
        budget_summary=budget_summary_records,
        intra_decile=intra_decile_records,
        detailed_budget=detailed_budget,
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
    from policyengine.outputs.aggregate import Aggregate as PEAggregate
    from policyengine.outputs.aggregate import AggregateType as PEAggregateType
    from policyengine.outputs.inequality import calculate_uk_inequality
    from policyengine.outputs.poverty import (
        calculate_uk_poverty_by_age,
        calculate_uk_poverty_by_gender,
        calculate_uk_poverty_rates,
    )
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

    # Run simulations (with optional regional filtering)
    pe_baseline_sim = PESimulation(
        dataset=pe_dataset,
        tax_benefit_model_version=pe_model_version,
        policy=baseline_policy,
        dynamic=baseline_dynamic,
        filter_field=baseline_sim.filter_field,
        filter_value=baseline_sim.filter_value,
    )
    pe_baseline_sim.ensure()

    pe_reform_sim = PESimulation(
        dataset=pe_dataset,
        tax_benefit_model_version=pe_model_version,
        policy=reform_policy,
        dynamic=reform_dynamic,
        filter_field=reform_sim.filter_field,
        filter_value=reform_sim.filter_value,
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
        "vat": {"entity": "household", "is_tax": True},
        "council_tax": {"entity": "household", "is_tax": True},
        "universal_credit": {"entity": "person", "is_tax": False},
        "child_benefit": {"entity": "person", "is_tax": False},
        "pension_credit": {"entity": "person", "is_tax": False},
        "income_support": {"entity": "person", "is_tax": False},
        "working_tax_credit": {"entity": "person", "is_tax": False},
        "child_tax_credit": {"entity": "person", "is_tax": False},
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

    # Calculate poverty rates for baseline and reform
    for pe_sim, db_sim in [
        (pe_baseline_sim, baseline_sim),
        (pe_reform_sim, reform_sim),
    ]:
        poverty_results = calculate_uk_poverty_rates(pe_sim)
        for pov in poverty_results.outputs:
            poverty_record = Poverty(
                simulation_id=db_sim.id,
                report_id=report.id,
                poverty_type=pov.poverty_type,
                entity=pov.entity,
                filter_variable=pov.filter_variable,
                headcount=pov.headcount,
                total_population=pov.total_population,
                rate=pov.rate,
            )
            session.add(poverty_record)

    # Calculate poverty rates by age group for baseline and reform
    for pe_sim, db_sim in [
        (pe_baseline_sim, baseline_sim),
        (pe_reform_sim, reform_sim),
    ]:
        age_poverty_results = calculate_uk_poverty_by_age(pe_sim)
        for pov in age_poverty_results.outputs:
            poverty_record = Poverty(
                simulation_id=db_sim.id,
                report_id=report.id,
                poverty_type=pov.poverty_type,
                entity=pov.entity,
                filter_variable=pov.filter_variable,
                headcount=pov.headcount,
                total_population=pov.total_population,
                rate=pov.rate,
            )
            session.add(poverty_record)

    # Calculate poverty rates by gender for baseline and reform
    for pe_sim, db_sim in [
        (pe_baseline_sim, baseline_sim),
        (pe_reform_sim, reform_sim),
    ]:
        gender_poverty_results = calculate_uk_poverty_by_gender(pe_sim)
        for pov in gender_poverty_results.outputs:
            poverty_record = Poverty(
                simulation_id=db_sim.id,
                report_id=report.id,
                poverty_type=pov.poverty_type,
                entity=pov.entity,
                filter_variable=pov.filter_variable,
                headcount=pov.headcount,
                total_population=pov.total_population,
                rate=pov.rate,
            )
            session.add(poverty_record)

    # Calculate inequality for baseline and reform
    for pe_sim, db_sim in [
        (pe_baseline_sim, baseline_sim),
        (pe_reform_sim, reform_sim),
    ]:
        ineq = calculate_uk_inequality(pe_sim)
        ineq.run()
        inequality_record = Inequality(
            simulation_id=db_sim.id,
            report_id=report.id,
            income_variable=ineq.income_variable,
            entity=ineq.entity,
            gini=ineq.gini,
            top_10_share=ineq.top_10_share,
            top_1_share=ineq.top_1_share,
            bottom_50_share=ineq.bottom_50_share,
        )
        session.add(inequality_record)

    # Calculate budget summary aggregates
    # UK budget variables — household-level aggregates for fiscal totals
    uk_budget_variables = {
        "household_tax": "household",
        "household_benefits": "household",
        "household_net_income": "household",
    }
    PEAggregate.model_rebuild(_types_namespace={"Simulation": PESimulation})
    for var_name, entity in uk_budget_variables.items():
        baseline_agg = PEAggregate(
            simulation=pe_baseline_sim,
            variable=var_name,
            aggregate_type=PEAggregateType.SUM,
            entity=entity,
        )
        baseline_agg.run()
        reform_agg = PEAggregate(
            simulation=pe_reform_sim,
            variable=var_name,
            aggregate_type=PEAggregateType.SUM,
            entity=entity,
        )
        reform_agg.run()
        budget_record = BudgetSummary(
            baseline_simulation_id=baseline_sim.id,
            reform_simulation_id=reform_sim.id,
            report_id=report.id,
            variable_name=var_name,
            entity=entity,
            baseline_total=float(baseline_agg.result),
            reform_total=float(reform_agg.result),
            change=float(reform_agg.result - baseline_agg.result),
        )
        session.add(budget_record)

    # Household count: bypass Aggregate and compute directly from raw numpy
    # values. Using Aggregate(SUM) on household_weight would compute
    # sum(weight * weight) because MicroSeries.sum() applies weights
    # automatically — it's unclear whether Aggregate can be used correctly
    # for summing the weight column itself.
    baseline_hh_count = float(
        pe_baseline_sim.output_dataset.data.household[
            "household_weight"
        ].values.sum()
    )
    reform_hh_count = float(
        pe_reform_sim.output_dataset.data.household[
            "household_weight"
        ].values.sum()
    )
    budget_record = BudgetSummary(
        baseline_simulation_id=baseline_sim.id,
        reform_simulation_id=reform_sim.id,
        report_id=report.id,
        variable_name="household_count_total",
        entity="household",
        baseline_total=baseline_hh_count,
        reform_total=reform_hh_count,
        change=reform_hh_count - baseline_hh_count,
    )
    session.add(budget_record)

    # Calculate intra-decile impact (5-category income change distribution)
    from policyengine_api.api.intra_decile import compute_intra_decile

    baseline_hh_data = {
        k: pe_baseline_sim.output_dataset.data.household[k].values
        for k in [
            "household_net_income",
            "household_weight",
            "household_count_people",
            "household_income_decile",
        ]
    }
    reform_hh_data = {
        k: pe_reform_sim.output_dataset.data.household[k].values
        for k in [
            "household_net_income",
            "household_weight",
            "household_count_people",
            "household_income_decile",
        ]
    }
    intra_decile_rows = compute_intra_decile(baseline_hh_data, reform_hh_data)
    for row in intra_decile_rows:
        record = IntraDecileImpact(
            baseline_simulation_id=baseline_sim.id,
            reform_simulation_id=reform_sim.id,
            report_id=report.id,
            **row,
        )
        session.add(record)

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


def _run_local_economy_comparison_us(job_id: str, session: Session) -> None:
    """Run US economy comparison analysis locally."""
    from datetime import datetime, timezone
    from uuid import UUID

    from policyengine.core import Simulation as PESimulation
    from policyengine.core.dynamic import Dynamic as PEDynamic
    from policyengine.core.policy import ParameterValue as PEParameterValue
    from policyengine.core.policy import Policy as PEPolicy
    from policyengine.outputs import DecileImpact as PEDecileImpact
    from policyengine.outputs.aggregate import Aggregate as PEAggregate
    from policyengine.outputs.aggregate import AggregateType as PEAggregateType
    from policyengine.outputs.inequality import calculate_us_inequality
    from policyengine.outputs.poverty import (
        calculate_us_poverty_by_age,
        calculate_us_poverty_by_gender,
        calculate_us_poverty_by_race,
        calculate_us_poverty_rates,
    )
    from policyengine.tax_benefit_models.us import us_latest
    from policyengine.tax_benefit_models.us.datasets import PolicyEngineUSDataset
    from policyengine.tax_benefit_models.us.outputs import (
        ProgramStatistics as PEProgramStats,
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

    pe_model_version = us_latest
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
    pe_dataset = PolicyEngineUSDataset(
        name=dataset.name,
        description=dataset.description or "",
        filepath=local_path,
        year=dataset.year,
    )

    # Run simulations (with optional regional filtering)
    pe_baseline_sim = PESimulation(
        dataset=pe_dataset,
        tax_benefit_model_version=pe_model_version,
        policy=baseline_policy,
        dynamic=baseline_dynamic,
        filter_field=baseline_sim.filter_field,
        filter_value=baseline_sim.filter_value,
    )
    pe_baseline_sim.ensure()

    pe_reform_sim = PESimulation(
        dataset=pe_dataset,
        tax_benefit_model_version=pe_model_version,
        policy=reform_policy,
        dynamic=reform_dynamic,
        filter_field=reform_sim.filter_field,
        filter_value=reform_sim.filter_value,
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
    PEProgramStats.model_rebuild(_types_namespace={"Simulation": PESimulation})
    programs = {
        "income_tax": {"entity": "tax_unit", "is_tax": True},
        "employee_payroll_tax": {"entity": "person", "is_tax": True},
        "snap": {"entity": "spm_unit", "is_tax": False},
        "tanf": {"entity": "spm_unit", "is_tax": False},
        "ssi": {"entity": "spm_unit", "is_tax": False},
        "social_security": {"entity": "person", "is_tax": False},
    }
    for prog_name, prog_info in programs.items():
        try:
            ps = PEProgramStats(
                baseline_simulation=pe_baseline_sim,
                reform_simulation=pe_reform_sim,
                program_name=prog_name,
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

    # Calculate poverty rates for baseline and reform
    for pe_sim, db_sim in [
        (pe_baseline_sim, baseline_sim),
        (pe_reform_sim, reform_sim),
    ]:
        poverty_results = calculate_us_poverty_rates(pe_sim)
        for pov in poverty_results.outputs:
            poverty_record = Poverty(
                simulation_id=db_sim.id,
                report_id=report.id,
                poverty_type=pov.poverty_type,
                entity=pov.entity,
                filter_variable=pov.filter_variable,
                headcount=pov.headcount,
                total_population=pov.total_population,
                rate=pov.rate,
            )
            session.add(poverty_record)

    # Calculate poverty rates by age group for baseline and reform
    for pe_sim, db_sim in [
        (pe_baseline_sim, baseline_sim),
        (pe_reform_sim, reform_sim),
    ]:
        age_poverty_results = calculate_us_poverty_by_age(pe_sim)
        for pov in age_poverty_results.outputs:
            poverty_record = Poverty(
                simulation_id=db_sim.id,
                report_id=report.id,
                poverty_type=pov.poverty_type,
                entity=pov.entity,
                filter_variable=pov.filter_variable,
                headcount=pov.headcount,
                total_population=pov.total_population,
                rate=pov.rate,
            )
            session.add(poverty_record)

    # Calculate poverty rates by gender for baseline and reform
    for pe_sim, db_sim in [
        (pe_baseline_sim, baseline_sim),
        (pe_reform_sim, reform_sim),
    ]:
        gender_poverty_results = calculate_us_poverty_by_gender(pe_sim)
        for pov in gender_poverty_results.outputs:
            poverty_record = Poverty(
                simulation_id=db_sim.id,
                report_id=report.id,
                poverty_type=pov.poverty_type,
                entity=pov.entity,
                filter_variable=pov.filter_variable,
                headcount=pov.headcount,
                total_population=pov.total_population,
                rate=pov.rate,
            )
            session.add(poverty_record)

    # Calculate poverty rates by race for baseline and reform (US only)
    for pe_sim, db_sim in [
        (pe_baseline_sim, baseline_sim),
        (pe_reform_sim, reform_sim),
    ]:
        race_poverty_results = calculate_us_poverty_by_race(pe_sim)
        for pov in race_poverty_results.outputs:
            poverty_record = Poverty(
                simulation_id=db_sim.id,
                report_id=report.id,
                poverty_type=pov.poverty_type,
                entity=pov.entity,
                filter_variable=pov.filter_variable,
                headcount=pov.headcount,
                total_population=pov.total_population,
                rate=pov.rate,
            )
            session.add(poverty_record)

    # Calculate inequality for baseline and reform
    for pe_sim, db_sim in [
        (pe_baseline_sim, baseline_sim),
        (pe_reform_sim, reform_sim),
    ]:
        ineq = calculate_us_inequality(pe_sim)
        ineq.run()
        inequality_record = Inequality(
            simulation_id=db_sim.id,
            report_id=report.id,
            income_variable=ineq.income_variable,
            entity=ineq.entity,
            gini=ineq.gini,
            top_10_share=ineq.top_10_share,
            top_1_share=ineq.top_1_share,
            bottom_50_share=ineq.bottom_50_share,
        )
        session.add(inequality_record)

    # Calculate budget summary aggregates
    # US budget variables — household-level plus state tax at tax_unit level
    us_budget_variables = {
        "household_tax": "household",
        "household_benefits": "household",
        "household_net_income": "household",
        "household_state_income_tax": "tax_unit",
    }
    PEAggregate.model_rebuild(_types_namespace={"Simulation": PESimulation})
    for var_name, entity in us_budget_variables.items():
        baseline_agg = PEAggregate(
            simulation=pe_baseline_sim,
            variable=var_name,
            aggregate_type=PEAggregateType.SUM,
            entity=entity,
        )
        baseline_agg.run()
        reform_agg = PEAggregate(
            simulation=pe_reform_sim,
            variable=var_name,
            aggregate_type=PEAggregateType.SUM,
            entity=entity,
        )
        reform_agg.run()
        budget_record = BudgetSummary(
            baseline_simulation_id=baseline_sim.id,
            reform_simulation_id=reform_sim.id,
            report_id=report.id,
            variable_name=var_name,
            entity=entity,
            baseline_total=float(baseline_agg.result),
            reform_total=float(reform_agg.result),
            change=float(reform_agg.result - baseline_agg.result),
        )
        session.add(budget_record)

    # Household count: bypass Aggregate and compute directly from raw numpy
    # values. Using Aggregate(SUM) on household_weight would compute
    # sum(weight * weight) because MicroSeries.sum() applies weights
    # automatically — it's unclear whether Aggregate can be used correctly
    # for summing the weight column itself.
    baseline_hh_count = float(
        pe_baseline_sim.output_dataset.data.household[
            "household_weight"
        ].values.sum()
    )
    reform_hh_count = float(
        pe_reform_sim.output_dataset.data.household[
            "household_weight"
        ].values.sum()
    )
    budget_record = BudgetSummary(
        baseline_simulation_id=baseline_sim.id,
        reform_simulation_id=reform_sim.id,
        report_id=report.id,
        variable_name="household_count_total",
        entity="household",
        baseline_total=baseline_hh_count,
        reform_total=reform_hh_count,
        change=reform_hh_count - baseline_hh_count,
    )
    session.add(budget_record)

    # Calculate intra-decile impact (5-category income change distribution)
    from policyengine_api.api.intra_decile import compute_intra_decile

    baseline_hh_data = {
        k: pe_baseline_sim.output_dataset.data.household[k].values
        for k in [
            "household_net_income",
            "household_weight",
            "household_count_people",
            "household_income_decile",
        ]
    }
    reform_hh_data = {
        k: pe_reform_sim.output_dataset.data.household[k].values
        for k in [
            "household_net_income",
            "household_weight",
            "household_count_people",
            "household_income_decile",
        ]
    }
    intra_decile_rows = compute_intra_decile(baseline_hh_data, reform_hh_data)
    for row in intra_decile_rows:
        record = IntraDecileImpact(
            baseline_simulation_id=baseline_sim.id,
            reform_simulation_id=reform_sim.id,
            report_id=report.id,
            **row,
        )
        session.add(record)

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
            _run_local_economy_comparison_us(job_id, session)
    else:
        # Use Modal
        import modal

        if tax_benefit_model_name == "policyengine_uk":
            fn = modal.Function.from_name("policyengine", "economy_comparison_uk")
        else:
            fn = modal.Function.from_name("policyengine", "economy_comparison_us")

        fn.spawn(job_id=job_id, traceparent=traceparent)


def _resolve_dataset_and_region(
    request: EconomicImpactRequest,
    session: Session,
) -> tuple[Dataset, Region | None]:
    """Resolve dataset from request, optionally via region lookup.

    Returns:
        Tuple of (dataset, region) where region is None if dataset_id was provided directly.
    """
    if request.region:
        # Look up region by code
        model_name = request.tax_benefit_model_name.replace("_", "-")
        region = session.exec(
            select(Region)
            .join(TaxBenefitModel)
            .where(Region.code == request.region)
            .where(TaxBenefitModel.name == model_name)
        ).first()

        if not region:
            raise HTTPException(
                status_code=404,
                detail=f"Region '{request.region}' not found for model {model_name}",
            )

        dataset = session.get(Dataset, region.dataset_id)
        if not dataset:
            raise HTTPException(
                status_code=404,
                detail=f"Dataset for region '{request.region}' not found",
            )
        return dataset, region

    elif request.dataset_id:
        dataset = session.get(Dataset, request.dataset_id)
        if not dataset:
            raise HTTPException(
                status_code=404, detail=f"Dataset {request.dataset_id} not found"
            )
        return dataset, None

    else:
        raise HTTPException(
            status_code=400,
            detail="Either dataset_id or region must be provided",
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

    You can specify the geographic scope either by:
    - dataset_id: Direct dataset reference
    - region: Region code (e.g., "state/ca", "us") which resolves to a dataset
    """
    # Resolve dataset (and optionally region)
    dataset, region = _resolve_dataset_and_region(request, session)

    # Extract filter parameters from region (if present)
    filter_field = region.filter_field if region and region.requires_filter else None
    filter_value = region.filter_value if region and region.requires_filter else None

    # Get model version
    model_version = _get_model_version(request.tax_benefit_model_name, session)

    # Get or create simulations using the resolved dataset
    baseline_sim = _get_or_create_simulation(
        simulation_type=SimulationType.ECONOMY,
        model_version_id=model_version.id,
        policy_id=None,
        dynamic_id=request.dynamic_id,
        session=session,
        dataset_id=dataset.id,
        filter_field=filter_field,
        filter_value=filter_value,
    )

    reform_sim = _get_or_create_simulation(
        simulation_type=SimulationType.ECONOMY,
        model_version_id=model_version.id,
        policy_id=request.policy_id,
        dynamic_id=request.dynamic_id,
        session=session,
        dataset_id=dataset.id,
        filter_field=filter_field,
        filter_value=filter_value,
    )

    # Get or create report
    label = f"Economic impact: {request.tax_benefit_model_name}"
    if request.policy_id:
        label += f" (policy {request.policy_id})"

    report = _get_or_create_report(
        baseline_sim.id, reform_sim.id, label, "economy_comparison", session
    )

    # Trigger computation if report is pending
    if report.status == ReportStatus.PENDING:
        with logfire.span("trigger_economy_comparison", job_id=str(report.id)):
            _trigger_economy_comparison(
                str(report.id), request.tax_benefit_model_name, session
            )

    return _build_response(report, baseline_sim, reform_sim, session, region)


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
