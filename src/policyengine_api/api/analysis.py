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
from pydantic import BaseModel, Field, model_validator
from sqlmodel import Session, select

from policyengine_api.api.module_registry import (
    MODULE_REGISTRY,
    get_modules_for_country,
    validate_modules,
)
from policyengine_api.models import (
    BudgetSummary,
    BudgetSummaryRead,
    CongressionalDistrictImpact,
    CongressionalDistrictImpactRead,
    ConstituencyImpact,
    ConstituencyImpactRead,
    Dataset,
    DecileImpact,
    DecileImpactRead,
    Inequality,
    InequalityRead,
    IntraDecileImpact,
    IntraDecileImpactRead,
    LocalAuthorityImpact,
    LocalAuthorityImpactRead,
    Poverty,
    PovertyRead,
    ProgramStatistics,
    ProgramStatisticsRead,
    Region,
    RegionDatasetLink,
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


# ---------------------------------------------------------------------------
# GET /analysis/options — list available computation modules
# ---------------------------------------------------------------------------


class ModuleOption(BaseModel):
    """A single computation module available for economy analysis."""

    name: str
    label: str
    description: str
    response_fields: list[str]


@router.get("/options", response_model=list[ModuleOption])
def list_analysis_options(
    country: str | None = None,
) -> list[ModuleOption]:
    """List available economy analysis modules.

    Args:
        country: Optional country code ('uk' or 'us') to filter modules.
    """
    if country:
        modules = get_modules_for_country(country)
    else:
        modules = list(MODULE_REGISTRY.values())

    return [
        ModuleOption(
            name=m.name,
            label=m.label,
            description=m.description,
            response_fields=list(m.response_fields),
        )
        for m in modules
    ]


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
    year: int | None = Field(
        default=None,
        description="Year for the analysis (e.g., 2026). Selects the dataset for that year. Uses latest available if omitted.",
    )

    @model_validator(mode="after")
    def check_dataset_or_region(self) -> "EconomicImpactRequest":
        if not self.dataset_id and not self.region:
            raise ValueError("Either dataset_id or region must be provided")
        return self


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
    congressional_district_impact: list[CongressionalDistrictImpactRead] | None = None
    constituency_impact: list[ConstituencyImpactRead] | None = None
    local_authority_impact: list[LocalAuthorityImpactRead] | None = None
    wealth_decile: list[DecileImpactRead] | None = None
    intra_wealth_decile: list[IntraDecileImpactRead] | None = None


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
    filter_strategy: str | None = None,
) -> UUID:
    """Generate a deterministic UUID from simulation parameters."""
    if simulation_type == SimulationType.ECONOMY:
        key = f"economy:{dataset_id}:{model_version_id}:{policy_id}:{dynamic_id}:{filter_field}:{filter_value}"
        # Only append filter_strategy when non-null to preserve backward
        # compatibility with existing simulation IDs
        if filter_strategy is not None:
            key += f":{filter_strategy}"
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
    filter_strategy: str | None = None,
    region_id: UUID | None = None,
    year: int | None = None,
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
        filter_strategy=filter_strategy,
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
        filter_strategy=filter_strategy,
        region_id=region_id,
        year=year,
    )
    from sqlalchemy.exc import IntegrityError

    session.add(simulation)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.get(Simulation, sim_id)
        if existing:
            return existing
        raise
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
    from sqlalchemy.exc import IntegrityError

    session.add(report)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.get(Report, report_id)
        if existing:
            return existing
        raise
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
    district_impact_records = None
    constituency_impact_records = None
    local_authority_impact_records = None
    wealth_decile_records = None
    intra_wealth_decile_records = None

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
            select(IntraDecileImpact).where(IntraDecileImpact.report_id == report.id)
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

        # Fetch congressional district impact records for this report
        district_rows = session.exec(
            select(CongressionalDistrictImpact).where(
                CongressionalDistrictImpact.report_id == report.id
            )
        ).all()
        if district_rows:
            district_impact_records = [
                CongressionalDistrictImpactRead(
                    id=d.id,
                    created_at=d.created_at,
                    baseline_simulation_id=d.baseline_simulation_id,
                    reform_simulation_id=d.reform_simulation_id,
                    report_id=d.report_id,
                    district_geoid=d.district_geoid,
                    state_fips=d.state_fips,
                    district_number=d.district_number,
                    average_household_income_change=_safe_float(
                        d.average_household_income_change
                    ),
                    relative_household_income_change=_safe_float(
                        d.relative_household_income_change
                    ),
                    population=_safe_float(d.population),
                )
                for d in district_rows
            ]

        # Fetch constituency impact records for this report
        constituency_rows = session.exec(
            select(ConstituencyImpact).where(ConstituencyImpact.report_id == report.id)
        ).all()
        if constituency_rows:
            constituency_impact_records = [
                ConstituencyImpactRead(
                    id=c.id,
                    created_at=c.created_at,
                    baseline_simulation_id=c.baseline_simulation_id,
                    reform_simulation_id=c.reform_simulation_id,
                    report_id=c.report_id,
                    constituency_code=c.constituency_code,
                    constituency_name=c.constituency_name,
                    x=c.x,
                    y=c.y,
                    average_household_income_change=_safe_float(
                        c.average_household_income_change
                    ),
                    relative_household_income_change=_safe_float(
                        c.relative_household_income_change
                    ),
                    population=_safe_float(c.population),
                )
                for c in constituency_rows
            ]

        # Fetch local authority impact records for this report
        la_rows = session.exec(
            select(LocalAuthorityImpact).where(
                LocalAuthorityImpact.report_id == report.id
            )
        ).all()
        if la_rows:
            local_authority_impact_records = [
                LocalAuthorityImpactRead(
                    id=la.id,
                    created_at=la.created_at,
                    baseline_simulation_id=la.baseline_simulation_id,
                    reform_simulation_id=la.reform_simulation_id,
                    report_id=la.report_id,
                    local_authority_code=la.local_authority_code,
                    local_authority_name=la.local_authority_name,
                    x=la.x,
                    y=la.y,
                    average_household_income_change=_safe_float(
                        la.average_household_income_change
                    ),
                    relative_household_income_change=_safe_float(
                        la.relative_household_income_change
                    ),
                    population=_safe_float(la.population),
                )
                for la in la_rows
            ]

        # Fetch wealth decile impact records (UK only)
        wealth_decile_rows = session.exec(
            select(DecileImpact).where(
                DecileImpact.report_id == report.id,
                DecileImpact.income_variable == "household_wealth_decile",
            )
        ).all()
        if wealth_decile_rows:
            wealth_decile_records = [
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
                for d in wealth_decile_rows
            ]

        # Fetch intra-wealth-decile records (UK only)
        intra_wealth_rows = session.exec(
            select(IntraDecileImpact).where(
                IntraDecileImpact.report_id == report.id,
                IntraDecileImpact.decile_type == "wealth",
            )
        ).all()
        if intra_wealth_rows:
            intra_wealth_decile_records = [
                IntraDecileImpactRead(
                    id=r.id,
                    created_at=r.created_at,
                    baseline_simulation_id=r.baseline_simulation_id,
                    reform_simulation_id=r.reform_simulation_id,
                    report_id=r.report_id,
                    decile_type=r.decile_type,
                    decile=r.decile,
                    lose_more_than_5pct=_safe_float(r.lose_more_than_5pct),
                    lose_less_than_5pct=_safe_float(r.lose_less_than_5pct),
                    no_change=_safe_float(r.no_change),
                    gain_less_than_5pct=_safe_float(r.gain_less_than_5pct),
                    gain_more_than_5pct=_safe_float(r.gain_more_than_5pct),
                )
                for r in intra_wealth_rows
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
        congressional_district_impact=district_impact_records,
        constituency_impact=constituency_impact_records,
        local_authority_impact=local_authority_impact_records,
        wealth_decile=wealth_decile_records,
        intra_wealth_decile=intra_wealth_decile_records,
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

    client = create_client(settings.supabase_url, settings.supabase_secret_key)
    data = client.storage.from_("datasets").download(filepath)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "wb") as f:
        f.write(data)

    return str(cache_path)


def _run_local_economy_comparison_uk(
    job_id: str, session: Session, modules: list[str] | None = None
) -> None:
    """Run UK economy comparison analysis locally."""
    from datetime import datetime, timezone
    from uuid import UUID

    from policyengine.core import Simulation as PESimulation
    from policyengine.core.dynamic import Dynamic as PEDynamic
    from policyengine.core.policy import ParameterValue as PEParameterValue
    from policyengine.core.policy import Policy as PEPolicy
    from policyengine.tax_benefit_models.uk import uk_latest
    from policyengine.tax_benefit_models.uk.datasets import PolicyEngineUKDataset

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
            raise ValueError(f"Policy {policy_id} not found in database")
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

    # Reconstruct scoping strategy from DB columns (if applicable)
    from policyengine_api.utils.strategy_reconstruction import reconstruct_strategy

    baseline_region = (
        session.get(Region, baseline_sim.region_id) if baseline_sim.region_id else None
    )
    baseline_strategy = reconstruct_strategy(
        filter_strategy=baseline_sim.filter_strategy,
        filter_field=baseline_sim.filter_field,
        filter_value=baseline_sim.filter_value,
        region_type=baseline_region.region_type.value if baseline_region else None,
    )

    reform_region = (
        session.get(Region, reform_sim.region_id) if reform_sim.region_id else None
    )
    reform_strategy = reconstruct_strategy(
        filter_strategy=reform_sim.filter_strategy,
        filter_field=reform_sim.filter_field,
        filter_value=reform_sim.filter_value,
        region_type=reform_region.region_type.value if reform_region else None,
    )

    # Run simulations (with optional regional scoping)
    pe_baseline_sim = PESimulation(
        dataset=pe_dataset,
        tax_benefit_model_version=pe_model_version,
        policy=baseline_policy,
        dynamic=baseline_dynamic,
        scoping_strategy=baseline_strategy,
        filter_field=baseline_sim.filter_field,
        filter_value=baseline_sim.filter_value,
    )
    pe_baseline_sim.ensure()

    pe_reform_sim = PESimulation(
        dataset=pe_dataset,
        tax_benefit_model_version=pe_model_version,
        policy=reform_policy,
        dynamic=reform_dynamic,
        scoping_strategy=reform_strategy,
        filter_field=reform_sim.filter_field,
        filter_value=reform_sim.filter_value,
    )
    pe_reform_sim.ensure()

    # Run computation modules
    from policyengine_api.api.computation_modules import UK_MODULE_DISPATCH, run_modules

    run_modules(
        dispatch=UK_MODULE_DISPATCH,
        modules=modules,
        pe_baseline_sim=pe_baseline_sim,
        pe_reform_sim=pe_reform_sim,
        baseline_sim_id=baseline_sim.id,
        reform_sim_id=reform_sim.id,
        report_id=report.id,
        session=session,
        country_id="uk",
    )

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


def _run_local_economy_comparison_us(
    job_id: str, session: Session, modules: list[str] | None = None
) -> None:
    """Run US economy comparison analysis locally."""
    from datetime import datetime, timezone
    from uuid import UUID

    from policyengine.core import Simulation as PESimulation
    from policyengine.core.dynamic import Dynamic as PEDynamic
    from policyengine.core.policy import ParameterValue as PEParameterValue
    from policyengine.core.policy import Policy as PEPolicy
    from policyengine.tax_benefit_models.us import us_latest
    from policyengine.tax_benefit_models.us.datasets import PolicyEngineUSDataset

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
            raise ValueError(f"Policy {policy_id} not found in database")
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

    # Reconstruct scoping strategy from DB columns (if applicable)
    from policyengine_api.utils.strategy_reconstruction import reconstruct_strategy

    baseline_region = (
        session.get(Region, baseline_sim.region_id) if baseline_sim.region_id else None
    )
    baseline_strategy = reconstruct_strategy(
        filter_strategy=baseline_sim.filter_strategy,
        filter_field=baseline_sim.filter_field,
        filter_value=baseline_sim.filter_value,
        region_type=baseline_region.region_type.value if baseline_region else None,
    )

    reform_region = (
        session.get(Region, reform_sim.region_id) if reform_sim.region_id else None
    )
    reform_strategy = reconstruct_strategy(
        filter_strategy=reform_sim.filter_strategy,
        filter_field=reform_sim.filter_field,
        filter_value=reform_sim.filter_value,
        region_type=reform_region.region_type.value if reform_region else None,
    )

    # Run simulations (with optional regional scoping)
    pe_baseline_sim = PESimulation(
        dataset=pe_dataset,
        tax_benefit_model_version=pe_model_version,
        policy=baseline_policy,
        dynamic=baseline_dynamic,
        scoping_strategy=baseline_strategy,
        filter_field=baseline_sim.filter_field,
        filter_value=baseline_sim.filter_value,
    )
    pe_baseline_sim.ensure()

    pe_reform_sim = PESimulation(
        dataset=pe_dataset,
        tax_benefit_model_version=pe_model_version,
        policy=reform_policy,
        dynamic=reform_dynamic,
        scoping_strategy=reform_strategy,
        filter_field=reform_sim.filter_field,
        filter_value=reform_sim.filter_value,
    )
    pe_reform_sim.ensure()

    # Run computation modules
    from policyengine_api.api.computation_modules import US_MODULE_DISPATCH, run_modules

    run_modules(
        dispatch=US_MODULE_DISPATCH,
        modules=modules,
        pe_baseline_sim=pe_baseline_sim,
        pe_reform_sim=pe_reform_sim,
        baseline_sim_id=baseline_sim.id,
        reform_sim_id=reform_sim.id,
        report_id=report.id,
        session=session,
        country_id="us",
    )

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
    job_id: str,
    tax_benefit_model_name: str,
    session: Session | None = None,
    modules: list[str] | None = None,
) -> None:
    """Trigger economy comparison analysis (local or Modal).

    Args:
        modules: Optional list of module names to run. If None, runs all.
    """
    from policyengine_api.config import settings

    traceparent = get_traceparent()

    if not settings.agent_use_modal and session is not None:
        # Run locally
        if tax_benefit_model_name == "policyengine_uk":
            _run_local_economy_comparison_uk(job_id, session, modules=modules)
        else:
            _run_local_economy_comparison_us(job_id, session, modules=modules)
    else:
        # Use Modal (modules param passed for future selective computation)
        import modal

        if tax_benefit_model_name == "policyengine_uk":
            fn = modal.Function.from_name(
                "policyengine",
                "economy_comparison_uk",
                environment_name=settings.modal_environment,
            )
        else:
            fn = modal.Function.from_name(
                "policyengine",
                "economy_comparison_us",
                environment_name=settings.modal_environment,
            )

        try:
            fn.spawn(job_id=job_id, traceparent=traceparent)
        except Exception as e:
            # Mark report as FAILED so it doesn't stay PENDING forever
            if session is not None:
                from uuid import UUID

                report = session.get(Report, UUID(job_id))
                if report:
                    report.status = ReportStatus.FAILED
                    report.error_message = f"Failed to trigger computation: {e}"
                    session.add(report)
                    session.commit()
            raise HTTPException(
                status_code=502,
                detail=f"Failed to trigger computation: {e}",
            )


def _resolve_dataset_and_region(
    request: EconomicImpactRequest,
    session: Session,
) -> tuple[Dataset, Region | None]:
    """Resolve dataset from request, optionally via region lookup.

    When a region is provided, the dataset is resolved from the region_datasets
    join table. If request.year is set, the dataset for that year is selected;
    otherwise the latest available year is used.

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

        # Resolve dataset from join table, filtered by year if provided
        query = (
            select(Dataset)
            .join(RegionDatasetLink)
            .where(RegionDatasetLink.region_id == region.id)
        )
        if request.year:
            query = query.where(Dataset.year == request.year)
        else:
            query = query.order_by(Dataset.year.desc())  # type: ignore
        dataset = session.exec(query).first()

        if not dataset:
            year_msg = f" for year {request.year}" if request.year else ""
            raise HTTPException(
                status_code=404,
                detail=f"No dataset found for region '{request.region}'{year_msg}",
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
    filter_strategy = (
        region.filter_strategy if region and region.requires_filter else None
    )

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
        filter_strategy=filter_strategy,
        region_id=region.id if region else None,
        year=dataset.year,
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
        filter_strategy=filter_strategy,
        region_id=region.id if region else None,
        year=dataset.year,
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

    region = (
        session.get(Region, baseline_sim.region_id) if baseline_sim.region_id else None
    )
    return _build_response(report, baseline_sim, reform_sim, session, region)


# ---------------------------------------------------------------------------
# POST /analysis/economy-custom — run selected economy modules
# ---------------------------------------------------------------------------

_MODEL_TO_COUNTRY = {
    "policyengine_uk": "uk",
    "policyengine_us": "us",
}


class EconomyCustomRequest(BaseModel):
    """Request body for custom economy analysis with selected modules."""

    tax_benefit_model_name: Literal["policyengine_uk", "policyengine_us"] = Field(
        description="Which country model to use"
    )
    dataset_id: UUID | None = Field(
        default=None,
        description="Dataset ID. Either dataset_id or region must be provided.",
    )
    region: str | None = Field(
        default=None,
        description="Region code (e.g., 'state/ca', 'us').",
    )
    policy_id: UUID | None = Field(
        default=None,
        description="Reform policy ID to compare against baseline (current law)",
    )
    dynamic_id: UUID | None = Field(
        default=None, description="Optional behavioural response specification ID"
    )
    year: int | None = Field(
        default=None,
        description="Year for the analysis. Uses latest available if omitted.",
    )
    modules: list[str] = Field(
        description="List of module names to compute (see GET /analysis/options)"
    )

    @model_validator(mode="after")
    def check_dataset_or_region(self) -> "EconomyCustomRequest":
        if not self.dataset_id and not self.region:
            raise ValueError("Either dataset_id or region must be provided")
        return self


def _build_filtered_response(
    full_response: EconomicImpactResponse,
    modules: list[str],
) -> EconomicImpactResponse:
    """Return a copy of the response with only the fields for requested modules."""
    allowed_fields: set[str] = set()
    for name in modules:
        module = MODULE_REGISTRY.get(name)
        if module:
            allowed_fields.update(module.response_fields)

    # Fields that are always included regardless of modules
    always_included = {
        "report_id",
        "status",
        "baseline_simulation",
        "reform_simulation",
        "region",
        "error_message",
    }

    filtered = {}
    for field_name in EconomicImpactResponse.model_fields:
        value = getattr(full_response, field_name)
        if field_name in always_included:
            filtered[field_name] = value
        elif field_name in allowed_fields:
            filtered[field_name] = value
        else:
            filtered[field_name] = None

    return EconomicImpactResponse.model_construct(**filtered)


@router.post("/economy-custom", response_model=EconomicImpactResponse)
def economy_custom(
    request: EconomyCustomRequest,
    session: Session = Depends(get_session),
) -> EconomicImpactResponse:
    """Run economy-wide analysis with only the selected modules.

    Same async pattern as /analysis/economic-impact but accepts a list of
    module names. Only the requested modules' response fields are populated;
    the rest are null.

    See GET /analysis/options for available module names.
    """
    country = _MODEL_TO_COUNTRY[request.tax_benefit_model_name]

    try:
        validate_modules(request.modules, country)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Reuse the same request model for dataset/region resolution
    impact_request = EconomicImpactRequest(
        tax_benefit_model_name=request.tax_benefit_model_name,
        dataset_id=request.dataset_id,
        region=request.region,
        policy_id=request.policy_id,
        dynamic_id=request.dynamic_id,
        year=request.year,
    )

    dataset, region_obj = _resolve_dataset_and_region(impact_request, session)

    filter_field = (
        region_obj.filter_field if region_obj and region_obj.requires_filter else None
    )
    filter_value = (
        region_obj.filter_value if region_obj and region_obj.requires_filter else None
    )
    filter_strategy = (
        region_obj.filter_strategy
        if region_obj and region_obj.requires_filter
        else None
    )

    model_version = _get_model_version(request.tax_benefit_model_name, session)

    baseline_sim = _get_or_create_simulation(
        simulation_type=SimulationType.ECONOMY,
        model_version_id=model_version.id,
        policy_id=None,
        dynamic_id=request.dynamic_id,
        session=session,
        dataset_id=dataset.id,
        filter_field=filter_field,
        filter_value=filter_value,
        filter_strategy=filter_strategy,
        region_id=region_obj.id if region_obj else None,
        year=dataset.year,
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
        filter_strategy=filter_strategy,
        region_id=region_obj.id if region_obj else None,
        year=dataset.year,
    )

    label = f"Custom analysis: {request.tax_benefit_model_name}"
    if request.policy_id:
        label += f" (policy {request.policy_id})"

    report = _get_or_create_report(
        baseline_sim.id, reform_sim.id, label, "economy_comparison", session
    )

    if report.status == ReportStatus.PENDING:
        with logfire.span("trigger_economy_comparison", job_id=str(report.id)):
            _trigger_economy_comparison(
                str(report.id),
                request.tax_benefit_model_name,
                session,
                modules=request.modules,
            )

    full_response = _build_response(
        report, baseline_sim, reform_sim, session, region_obj
    )
    return _build_filtered_response(full_response, request.modules)


@router.get("/economy-custom/{report_id}", response_model=EconomicImpactResponse)
def get_economy_custom_status(
    report_id: UUID,
    modules: str | None = None,
    session: Session = Depends(get_session),
) -> EconomicImpactResponse:
    """Poll for results of custom economy analysis.

    Args:
        report_id: The report ID returned by POST /analysis/economy-custom.
        modules: Optional comma-separated module names to filter the response.
            If omitted, all computed fields are returned.
    """
    report = session.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

    if not report.baseline_simulation_id or not report.reform_simulation_id:
        raise HTTPException(status_code=500, detail="Report missing simulation IDs")

    baseline_sim = session.get(Simulation, report.baseline_simulation_id)
    reform_sim = session.get(Simulation, report.reform_simulation_id)

    if not baseline_sim or not reform_sim:
        raise HTTPException(status_code=500, detail="Simulation data missing")

    region = (
        session.get(Region, baseline_sim.region_id) if baseline_sim.region_id else None
    )
    full_response = _build_response(report, baseline_sim, reform_sim, session, region)

    if modules:
        module_list = [m.strip() for m in modules.split(",")]
        return _build_filtered_response(full_response, module_list)

    return full_response


# ---------------------------------------------------------------------------
# POST /analysis/rerun/{report_id} — force-rerun a report
# ---------------------------------------------------------------------------


class RerunResponse(BaseModel):
    """Response from the rerun endpoint."""

    report_id: str
    status: str


@router.post("/rerun/{report_id}", response_model=RerunResponse)
def rerun_report(
    report_id: UUID,
    session: Session = Depends(get_session),
) -> RerunResponse:
    """Force-rerun a report from scratch.

    Resets the report and its simulations to PENDING, deletes all
    previously computed result records, and re-triggers computation.
    Works for both economy and household reports.
    """
    from sqlmodel import delete

    from policyengine_api.api.household_analysis import _trigger_household_impact

    # 1. Load report
    report = session.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

    # 2. Load simulations
    baseline_sim = (
        session.get(Simulation, report.baseline_simulation_id)
        if report.baseline_simulation_id
        else None
    )
    reform_sim = (
        session.get(Simulation, report.reform_simulation_id)
        if report.reform_simulation_id
        else None
    )

    if not baseline_sim:
        raise HTTPException(status_code=400, detail="Report has no baseline simulation")

    # 3. Derive tax_benefit_model_name from simulation → model version → model
    model_version = session.get(
        TaxBenefitModelVersion, baseline_sim.tax_benefit_model_version_id
    )
    if not model_version:
        raise HTTPException(status_code=500, detail="Model version not found")

    model = session.get(TaxBenefitModel, model_version.model_id)
    if not model:
        raise HTTPException(status_code=500, detail="Tax-benefit model not found")

    tax_benefit_model_name = model.name.replace("-", "_")

    # 4. Delete all result records for this report
    result_tables = [
        DecileImpact,
        ProgramStatistics,
        Poverty,
        Inequality,
        BudgetSummary,
        IntraDecileImpact,
        CongressionalDistrictImpact,
        ConstituencyImpact,
        LocalAuthorityImpact,
    ]
    for table in result_tables:
        session.exec(delete(table).where(table.report_id == report_id))

    # 5. Reset report status
    report.status = ReportStatus.PENDING
    report.error_message = None
    session.add(report)

    # 6. Reset simulation statuses
    for sim in [baseline_sim, reform_sim]:
        if sim:
            sim.status = SimulationStatus.PENDING
            sim.error_message = None
            sim.completed_at = None
            session.add(sim)

    session.commit()

    # 7. Trigger computation based on report type
    is_economy = report.report_type and "economy" in report.report_type
    is_household = report.report_type and "household" in report.report_type

    if is_economy:
        with logfire.span("rerun_economy_comparison", job_id=str(report.id)):
            _trigger_economy_comparison(str(report.id), tax_benefit_model_name, session)
    elif is_household:
        with logfire.span("rerun_household_impact", job_id=str(report.id)):
            _trigger_household_impact(str(report.id), tax_benefit_model_name, session)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown report type: {report.report_type}",
        )

    return RerunResponse(report_id=str(report_id), status="pending")
