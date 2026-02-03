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
from datetime import datetime, timezone
from typing import Any, Literal
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
    Household,
    Policy,
    ProgramStatistics,
    ProgramStatisticsRead,
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
) -> UUID:
    """Generate a deterministic UUID from simulation parameters."""
    if simulation_type == SimulationType.ECONOMY:
        key = f"economy:{dataset_id}:{model_version_id}:{policy_id}:{dynamic_id}"
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
) -> Simulation:
    """Get existing simulation or create a new one."""
    sim_id = _get_deterministic_simulation_id(
        simulation_type,
        model_version_id,
        policy_id,
        dynamic_id,
        dataset_id=dataset_id,
        household_id=household_id,
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


# Entity types by country
UK_ENTITIES = ["person", "benunit", "household"]
US_ENTITIES = ["person", "tax_unit", "spm_unit", "family", "marital_unit", "household"]


def _compute_entity_diff(
    baseline_list: list[dict],
    reform_list: list[dict],
) -> list[dict]:
    """Compute per-variable diffs for a list of entity instances."""
    entity_impact = []

    for b_entity, r_entity in zip(baseline_list, reform_list):
        entity_diff = {}
        for key in b_entity:
            if key in r_entity:
                baseline_val = b_entity[key]
                reform_val = r_entity[key]
                if isinstance(baseline_val, (int, float)) and isinstance(
                    reform_val, (int, float)
                ):
                    entity_diff[key] = {
                        "baseline": baseline_val,
                        "reform": reform_val,
                        "change": reform_val - baseline_val,
                    }
        entity_impact.append(entity_diff)

    return entity_impact


def _compute_household_impact(
    baseline_result: dict,
    reform_result: dict,
    country: str,
) -> dict[str, Any]:
    """Compute difference between baseline and reform for all entity types."""
    entities = UK_ENTITIES if country == "uk" else US_ENTITIES

    impact: dict[str, Any] = {}

    for entity in entities:
        if entity in baseline_result and entity in reform_result:
            impact[entity] = _compute_entity_diff(
                baseline_result[entity],
                reform_result[entity],
            )

    return impact


def _ensure_list(value: Any) -> list:
    """Ensure value is a list; wrap dict in list if needed."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _run_household_simulation(simulation_id: UUID, session: Session) -> None:
    """Run a single household simulation and store result."""
    from policyengine_api.api.household import (
        _calculate_household_uk,
        _calculate_household_us,
    )

    simulation = session.get(Simulation, simulation_id)
    if not simulation:
        raise ValueError(f"Simulation {simulation_id} not found")

    household = session.get(Household, simulation.household_id)
    if not household:
        raise ValueError(f"Household {simulation.household_id} not found")

    # Update status
    simulation.status = SimulationStatus.RUNNING
    simulation.started_at = datetime.now(timezone.utc)
    session.add(simulation)
    session.commit()

    try:
        # Get policy if set
        policy_data = None
        if simulation.policy_id:
            policy = session.get(Policy, simulation.policy_id)
            if policy and policy.parameter_values:
                policy_data = {}
                for pv in policy.parameter_values:
                    if pv.parameter:
                        param_name = pv.parameter.name
                        policy_data[param_name] = {
                            "value": pv.value_json.get("value")
                            if isinstance(pv.value_json, dict)
                            else pv.value_json,
                            "start_date": pv.start_date.isoformat()
                            if pv.start_date
                            else None,
                            "end_date": pv.end_date.isoformat()
                            if pv.end_date
                            else None,
                        }

        # Extract household data with list conversion
        data = household.household_data
        people = data.get("people", [])

        # Run calculation based on country
        if household.tax_benefit_model_name == "policyengine_uk":
            result = _calculate_household_uk(
                people=people,
                benunit=_ensure_list(data.get("benunit")),
                household=_ensure_list(data.get("household")),
                year=household.year,
                policy_data=policy_data,
            )
        else:
            result = _calculate_household_us(
                people=people,
                marital_unit=_ensure_list(data.get("marital_unit")),
                family=_ensure_list(data.get("family")),
                spm_unit=_ensure_list(data.get("spm_unit")),
                tax_unit=_ensure_list(data.get("tax_unit")),
                household=_ensure_list(data.get("household")),
                year=household.year,
                policy_data=policy_data,
            )

        # Store result
        simulation.household_result = result
        simulation.status = SimulationStatus.COMPLETED
        simulation.completed_at = datetime.now(timezone.utc)

    except Exception as e:
        simulation.status = SimulationStatus.FAILED
        simulation.error_message = str(e)
        simulation.completed_at = datetime.now(timezone.utc)

    session.add(simulation)
    session.commit()


def _trigger_household_report(report_id: UUID, session: Session) -> None:
    """Trigger household simulation(s) for a report."""
    report = session.get(Report, report_id)
    if not report:
        raise ValueError(f"Report {report_id} not found")

    # Update report status
    report.status = ReportStatus.RUNNING
    session.add(report)
    session.commit()

    try:
        # Run baseline
        baseline_sim = session.get(Simulation, report.baseline_simulation_id)
        if baseline_sim and baseline_sim.status == SimulationStatus.PENDING:
            _run_household_simulation(baseline_sim.id, session)

        # Run reform if exists
        if report.reform_simulation_id:
            reform_sim = session.get(Simulation, report.reform_simulation_id)
            if reform_sim and reform_sim.status == SimulationStatus.PENDING:
                _run_household_simulation(reform_sim.id, session)

        # Update report status
        report.status = ReportStatus.COMPLETED
    except Exception as e:
        report.status = ReportStatus.FAILED
        report.error_message = str(e)

    session.add(report)
    session.commit()


# Household impact request/response schemas
class HouseholdImpactRequest(BaseModel):
    """Request for household impact analysis."""

    household_id: UUID = Field(description="ID of the household to analyze")
    policy_id: UUID | None = Field(
        default=None,
        description="Reform policy ID. If None, runs single calculation under current law.",
    )
    dynamic_id: UUID | None = Field(
        default=None, description="Optional behavioural response specification ID"
    )


class HouseholdSimulationInfo(BaseModel):
    """Info about a household simulation."""

    id: UUID
    status: SimulationStatus
    error_message: str | None = None


class HouseholdImpactResponse(BaseModel):
    """Response for household impact analysis."""

    report_id: UUID
    report_type: str
    status: ReportStatus
    baseline_simulation: HouseholdSimulationInfo | None = None
    reform_simulation: HouseholdSimulationInfo | None = None
    baseline_result: dict | None = None
    reform_result: dict | None = None
    impact: dict | None = None
    error_message: str | None = None


def _build_household_response(
    report: Report,
    baseline_sim: Simulation,
    reform_sim: Simulation | None,
    session: Session,
) -> HouseholdImpactResponse:
    """Build response including computed impact for comparisons."""
    baseline_result = baseline_sim.household_result if baseline_sim else None
    reform_result = reform_sim.household_result if reform_sim else None

    # Compute impact if comparison and both complete
    impact = None
    if reform_sim and baseline_result and reform_result:
        # Determine country from household
        household = session.get(Household, baseline_sim.household_id)
        if household:
            country = (
                "uk" if household.tax_benefit_model_name == "policyengine_uk" else "us"
            )
            impact = _compute_household_impact(baseline_result, reform_result, country)

    return HouseholdImpactResponse(
        report_id=report.id,
        report_type=report.report_type or "household_single",
        status=report.status,
        baseline_simulation=HouseholdSimulationInfo(
            id=baseline_sim.id,
            status=baseline_sim.status,
            error_message=baseline_sim.error_message,
        )
        if baseline_sim
        else None,
        reform_simulation=HouseholdSimulationInfo(
            id=reform_sim.id,
            status=reform_sim.status,
            error_message=reform_sim.error_message,
        )
        if reform_sim
        else None,
        baseline_result=baseline_result,
        reform_result=reform_result,
        impact=impact,
        error_message=report.error_message,
    )


@router.post("/household-impact", response_model=HouseholdImpactResponse)
def household_impact(
    request: HouseholdImpactRequest,
    session: Session = Depends(get_session),
) -> HouseholdImpactResponse:
    """Run household impact analysis.

    If policy_id is None: single run under current law.
    If policy_id is set: comparison (baseline vs reform).

    This is a synchronous operation for household calculations.
    """
    # Validate household exists
    household = session.get(Household, request.household_id)
    if not household:
        raise HTTPException(
            status_code=404, detail=f"Household {request.household_id} not found"
        )

    # Validate policy if provided
    if request.policy_id:
        policy = session.get(Policy, request.policy_id)
        if not policy:
            raise HTTPException(
                status_code=404, detail=f"Policy {request.policy_id} not found"
            )

    # Get model version from household's tax_benefit_model_name
    model_version = _get_model_version(household.tax_benefit_model_name, session)

    # Create baseline simulation
    baseline_sim = _get_or_create_simulation(
        simulation_type=SimulationType.HOUSEHOLD,
        model_version_id=model_version.id,
        policy_id=None,
        dynamic_id=request.dynamic_id,
        session=session,
        household_id=request.household_id,
    )

    # Create reform simulation if policy_id provided
    reform_sim = None
    if request.policy_id:
        reform_sim = _get_or_create_simulation(
            simulation_type=SimulationType.HOUSEHOLD,
            model_version_id=model_version.id,
            policy_id=request.policy_id,
            dynamic_id=request.dynamic_id,
            session=session,
            household_id=request.household_id,
        )

    # Determine report type
    report_type = "household_comparison" if request.policy_id else "household_single"

    # Create report
    label = f"Household impact: {household.tax_benefit_model_name}"
    report = _get_or_create_report(
        baseline_sim_id=baseline_sim.id,
        reform_sim_id=reform_sim.id if reform_sim else None,
        label=label,
        report_type=report_type,
        session=session,
    )

    # Trigger compute if pending
    if report.status == ReportStatus.PENDING:
        with logfire.span("trigger_household_report", job_id=str(report.id)):
            _trigger_household_report(report.id, session)

    return _build_household_response(report, baseline_sim, reform_sim, session)


@router.get("/household-impact/{report_id}", response_model=HouseholdImpactResponse)
def get_household_impact(
    report_id: UUID,
    session: Session = Depends(get_session),
) -> HouseholdImpactResponse:
    """Get household impact analysis status and results."""
    report = session.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

    if not report.baseline_simulation_id:
        raise HTTPException(
            status_code=500, detail="Report missing baseline simulation ID"
        )

    baseline_sim = session.get(Simulation, report.baseline_simulation_id)
    if not baseline_sim:
        raise HTTPException(status_code=500, detail="Baseline simulation data missing")

    reform_sim = None
    if report.reform_simulation_id:
        reform_sim = session.get(Simulation, report.reform_simulation_id)

    return _build_household_response(report, baseline_sim, reform_sim, session)


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
        simulation_type=SimulationType.ECONOMY,
        model_version_id=model_version.id,
        policy_id=None,
        dynamic_id=request.dynamic_id,
        session=session,
        dataset_id=request.dataset_id,
    )

    reform_sim = _get_or_create_simulation(
        simulation_type=SimulationType.ECONOMY,
        model_version_id=model_version.id,
        policy_id=request.policy_id,
        dynamic_id=request.dynamic_id,
        session=session,
        dataset_id=request.dataset_id,
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
