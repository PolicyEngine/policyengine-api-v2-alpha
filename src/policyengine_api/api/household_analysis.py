"""Household impact analysis endpoints.

Use these endpoints to analyze household-level effects of policy reforms.
Supports single runs (current law) and comparisons (baseline vs reform).

WORKFLOW:
1. Create a stored household: POST /households
2. Optionally create a reform policy: POST /policies
3. Run analysis: POST /analysis/household-impact (returns report_id)
4. Poll GET /analysis/household-impact/{report_id} until status="completed"
5. Results include baseline_result, reform_result (if comparison), and impact diff
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID

import logfire
from fastapi import APIRouter, Depends, HTTPException
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from pydantic import BaseModel, Field
from sqlmodel import Session

from policyengine_api.models import (
    Household,
    Policy,
    Report,
    ReportStatus,
    Simulation,
    SimulationStatus,
    SimulationType,
)
from policyengine_api.services.database import get_session

from .analysis import (
    _get_model_version,
    _get_or_create_report,
    _get_or_create_simulation,
)


def get_traceparent() -> str | None:
    """Get the current W3C traceparent header for distributed tracing."""
    carrier: dict[str, str] = {}
    TraceContextTextMapPropagator().inject(carrier)
    return carrier.get("traceparent")


router = APIRouter(prefix="/analysis", tags=["analysis"])


# =============================================================================
# Country Strategy Pattern
# =============================================================================


@dataclass(frozen=True)
class CountryConfig:
    """Configuration for a country's household calculation."""

    name: str
    entity_types: tuple[str, ...]


UK_CONFIG = CountryConfig(
    name="uk",
    entity_types=("person", "benunit", "household"),
)

US_CONFIG = CountryConfig(
    name="us",
    entity_types=(
        "person",
        "tax_unit",
        "spm_unit",
        "family",
        "marital_unit",
        "household",
    ),
)


def get_country_config(tax_benefit_model_name: str) -> CountryConfig:
    """Get country configuration from model name."""
    if tax_benefit_model_name == "policyengine_uk":
        return UK_CONFIG
    return US_CONFIG


class HouseholdCalculator(Protocol):
    """Protocol for country-specific household calculators."""

    def __call__(
        self,
        household_data: dict[str, Any],
        year: int,
        policy_data: dict | None,
    ) -> dict: ...


def calculate_uk_household(
    household_data: dict[str, Any],
    year: int,
    policy_data: dict | None,
) -> dict:
    """Calculate UK household using the existing implementation."""
    from policyengine_api.api.household import _calculate_household_uk

    return _calculate_household_uk(
        people=household_data.get("people", []),
        benunit=_ensure_list(household_data.get("benunit")),
        household=_ensure_list(household_data.get("household")),
        year=year,
        policy_data=policy_data,
    )


def calculate_us_household(
    household_data: dict[str, Any],
    year: int,
    policy_data: dict | None,
) -> dict:
    """Calculate US household using the existing implementation."""
    from policyengine_api.api.household import _calculate_household_us

    return _calculate_household_us(
        people=household_data.get("people", []),
        marital_unit=_ensure_list(household_data.get("marital_unit")),
        family=_ensure_list(household_data.get("family")),
        spm_unit=_ensure_list(household_data.get("spm_unit")),
        tax_unit=_ensure_list(household_data.get("tax_unit")),
        household=_ensure_list(household_data.get("household")),
        year=year,
        policy_data=policy_data,
    )


def get_calculator(tax_benefit_model_name: str) -> HouseholdCalculator:
    """Get the appropriate calculator for a country."""
    if tax_benefit_model_name == "policyengine_uk":
        return calculate_uk_household
    return calculate_us_household


# =============================================================================
# Data Transformation Helpers
# =============================================================================


def _ensure_list(value: Any) -> list:
    """Ensure value is a list; wrap dict in list if needed."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _extract_policy_data(policy: Policy | None) -> dict | None:
    """Extract policy data from a Policy model into calculation format.

    Returns format expected by _calculate_household_us/_calculate_household_uk:
    {
        "name": "policy name",
        "description": "policy description",
        "parameter_values": [
            {
                "parameter_name": "gov.irs.credits.ctc...",
                "value": 0.16,
                "start_date": "2024-01-01T00:00:00+00:00",
                "end_date": null
            }
        ]
    }
    """
    if not policy or not policy.parameter_values:
        return None

    parameter_values = []
    for pv in policy.parameter_values:
        if not pv.parameter:
            continue

        parameter_values.append(
            {
                "parameter_name": pv.parameter.name,
                "value": _extract_value(pv.value_json),
                "start_date": _format_date(pv.start_date),
                "end_date": _format_date(pv.end_date),
            }
        )

    if not parameter_values:
        return None

    return {
        "name": policy.name,
        "description": policy.description or "",
        "parameter_values": parameter_values,
    }


def _extract_value(value_json: Any) -> Any:
    """Extract the actual value from value_json."""
    if isinstance(value_json, dict):
        return value_json.get("value")
    return value_json


def _format_date(date: Any) -> str | None:
    """Format a date for the policy data structure."""
    if date is None:
        return None
    if hasattr(date, "isoformat"):
        return date.isoformat()
    return str(date)


# =============================================================================
# Impact Computation
# =============================================================================


def compute_variable_diff(baseline_val: Any, reform_val: Any) -> dict | None:
    """Compute diff for a single variable if both are numeric."""
    if not isinstance(baseline_val, (int, float)):
        return None
    if not isinstance(reform_val, (int, float)):
        return None

    return {
        "baseline": baseline_val,
        "reform": reform_val,
        "change": reform_val - baseline_val,
    }


def compute_entity_diff(baseline_entity: dict, reform_entity: dict) -> dict:
    """Compute per-variable diffs for a single entity instance."""
    entity_diff = {}

    for key, baseline_val in baseline_entity.items():
        reform_val = reform_entity.get(key)
        if reform_val is None:
            continue

        diff = compute_variable_diff(baseline_val, reform_val)
        if diff is not None:
            entity_diff[key] = diff

    return entity_diff


def compute_entity_list_diff(
    baseline_list: list[dict],
    reform_list: list[dict],
) -> list[dict]:
    """Compute diffs for a list of entity instances."""
    return [
        compute_entity_diff(b_entity, r_entity)
        for b_entity, r_entity in zip(baseline_list, reform_list)
    ]


def compute_household_impact(
    baseline_result: dict,
    reform_result: dict,
    config: CountryConfig,
) -> dict[str, Any]:
    """Compute difference between baseline and reform for all entity types."""
    impact: dict[str, Any] = {}

    for entity in config.entity_types:
        baseline_entities = baseline_result.get(entity)
        reform_entities = reform_result.get(entity)

        if baseline_entities is None or reform_entities is None:
            continue

        impact[entity] = compute_entity_list_diff(baseline_entities, reform_entities)

    return impact


# =============================================================================
# Simulation Execution
# =============================================================================


def mark_simulation_running(simulation: Simulation, session: Session) -> None:
    """Mark a simulation as running."""
    simulation.status = SimulationStatus.RUNNING
    simulation.started_at = datetime.now(timezone.utc)
    session.add(simulation)
    session.commit()


def mark_simulation_completed(
    simulation: Simulation,
    result: dict,
    session: Session,
) -> None:
    """Mark a simulation as completed with result."""
    simulation.household_result = result
    simulation.status = SimulationStatus.COMPLETED
    simulation.completed_at = datetime.now(timezone.utc)
    session.add(simulation)
    session.commit()


def mark_simulation_failed(
    simulation: Simulation,
    error: Exception,
    session: Session,
) -> None:
    """Mark a simulation as failed with error."""
    simulation.status = SimulationStatus.FAILED
    simulation.error_message = str(error)
    simulation.completed_at = datetime.now(timezone.utc)
    session.add(simulation)
    session.commit()


def run_household_simulation(simulation_id: UUID, session: Session) -> None:
    """Run a single household simulation and store result."""
    simulation = _load_simulation(simulation_id, session)
    household = _load_household(simulation.household_id, session)
    policy_data = _load_policy_data(simulation.policy_id, session)

    mark_simulation_running(simulation, session)

    try:
        calculator = get_calculator(household.tax_benefit_model_name)
        result = calculator(household.household_data, household.year, policy_data)
        mark_simulation_completed(simulation, result, session)
    except Exception as e:
        logfire.error(
            "Household simulation failed",
            simulation_id=str(simulation_id),
            error=str(e),
        )
        mark_simulation_failed(simulation, e, session)


def _load_simulation(simulation_id: UUID, session: Session) -> Simulation:
    """Load simulation or raise error."""
    simulation = session.get(Simulation, simulation_id)
    if not simulation:
        raise ValueError(f"Simulation {simulation_id} not found")
    return simulation


def _load_household(household_id: UUID | None, session: Session) -> Household:
    """Load household or raise error."""
    if not household_id:
        raise ValueError("Simulation has no household_id")

    household = session.get(Household, household_id)
    if not household:
        raise ValueError(f"Household {household_id} not found")
    return household


def _load_policy_data(policy_id: UUID | None, session: Session) -> dict | None:
    """Load and extract policy data if policy_id is set."""
    if not policy_id:
        return None

    policy = session.get(Policy, policy_id)
    return _extract_policy_data(policy)


# =============================================================================
# Report Orchestration (Async)
# =============================================================================


def _run_local_household_impact(report_id: str, session: Session) -> None:
    """Run household impact analysis locally.

    NOTE: This runs synchronously and blocks the HTTP request when running
    locally (agent_use_modal=False). This mirrors the economic impact behavior.
    True async execution requires Modal.
    """
    report = session.get(Report, UUID(report_id))
    if not report:
        raise ValueError(f"Report {report_id} not found for household impact")

    report.status = ReportStatus.RUNNING
    session.add(report)
    session.commit()

    try:
        # Run baseline simulation
        if report.baseline_simulation_id:
            _run_simulation_in_session(report.baseline_simulation_id, session)

        # Run reform simulation if present
        if report.reform_simulation_id:
            _run_simulation_in_session(report.reform_simulation_id, session)

        report.status = ReportStatus.COMPLETED
        session.add(report)
        session.commit()
    except Exception as e:
        report.status = ReportStatus.FAILED
        report.error_message = str(e)
        session.add(report)
        session.commit()


def _run_simulation_in_session(simulation_id: UUID, session: Session) -> None:
    """Run a single household simulation within an existing session."""
    simulation = session.get(Simulation, simulation_id)
    if not simulation or simulation.status != SimulationStatus.PENDING:
        return

    household = session.get(Household, simulation.household_id)
    if not household:
        raise ValueError(f"Household {simulation.household_id} not found")

    policy_data = _load_policy_data(simulation.policy_id, session)

    simulation.status = SimulationStatus.RUNNING
    simulation.started_at = datetime.now(timezone.utc)
    session.add(simulation)
    session.commit()

    try:
        calculator = get_calculator(household.tax_benefit_model_name)
        result = calculator(household.household_data, household.year, policy_data)

        simulation.household_result = result
        simulation.status = SimulationStatus.COMPLETED
        simulation.completed_at = datetime.now(timezone.utc)
        session.add(simulation)
        session.commit()
    except Exception as e:
        simulation.status = SimulationStatus.FAILED
        simulation.error_message = str(e)
        simulation.completed_at = datetime.now(timezone.utc)
        session.add(simulation)
        session.commit()
        raise


def _trigger_household_impact(
    report_id: str, tax_benefit_model_name: str, session: Session | None = None
) -> None:
    """Trigger household impact calculation (local or Modal based on settings)."""
    from policyengine_api.config import settings

    traceparent = get_traceparent()

    if not settings.agent_use_modal and session is not None:
        # Run locally (blocking - see _run_local_household_impact docstring)
        _run_local_household_impact(report_id, session)
    else:
        # Use Modal
        import modal

        if tax_benefit_model_name == "policyengine_uk":
            fn = modal.Function.from_name(
                "policyengine",
                "household_impact_uk",
                environment_name=settings.modal_environment,
            )
        else:
            fn = modal.Function.from_name(
                "policyengine",
                "household_impact_us",
                environment_name=settings.modal_environment,
            )

        try:
            fn.spawn(report_id=report_id, traceparent=traceparent)
        except Exception as e:
            # Mark report as FAILED so it doesn't stay PENDING forever
            if session is not None:
                report = session.get(Report, UUID(report_id))
                if report:
                    report.status = ReportStatus.FAILED
                    report.error_message = f"Failed to trigger computation: {e}"
                    session.add(report)
                    session.commit()
            raise HTTPException(
                status_code=502,
                detail=f"Failed to trigger computation: {e}",
            )


# Legacy functions kept for compatibility
def _load_report(report_id: UUID, session: Session) -> Report:
    """Load report or raise error."""
    report = session.get(Report, report_id)
    if not report:
        raise ValueError(f"Report {report_id} not found")
    return report


# =============================================================================
# Request/Response Schemas
# =============================================================================


class HouseholdImpactRequest(BaseModel):
    """Request for household impact analysis."""

    household_id: UUID = Field(description="ID of the household to analyze")
    policy_id: UUID | None = Field(
        default=None,
        description="Reform policy ID. If None, runs single calculation under current law.",
    )
    dynamic_id: UUID | None = Field(
        default=None,
        description="Optional behavioural response specification ID",
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


# =============================================================================
# Response Building
# =============================================================================


def build_simulation_info(
    simulation: Simulation | None,
) -> HouseholdSimulationInfo | None:
    """Build simulation info from a simulation."""
    if not simulation:
        return None

    return HouseholdSimulationInfo(
        id=simulation.id,
        status=simulation.status,
        error_message=simulation.error_message,
    )


def build_household_response(
    report: Report,
    baseline_sim: Simulation,
    reform_sim: Simulation | None,
    session: Session,
) -> HouseholdImpactResponse:
    """Build response including computed impact for comparisons."""
    baseline_result = baseline_sim.household_result
    reform_result = reform_sim.household_result if reform_sim else None

    impact = _compute_impact_if_comparison(
        baseline_sim, reform_sim, baseline_result, reform_result, session
    )

    return HouseholdImpactResponse(
        report_id=report.id,
        report_type=report.report_type or "household_single",
        status=report.status,
        baseline_simulation=build_simulation_info(baseline_sim),
        reform_simulation=build_simulation_info(reform_sim),
        baseline_result=baseline_result,
        reform_result=reform_result,
        impact=impact,
        error_message=report.error_message,
    )


def _compute_impact_if_comparison(
    baseline_sim: Simulation,
    reform_sim: Simulation | None,
    baseline_result: dict | None,
    reform_result: dict | None,
    session: Session,
) -> dict | None:
    """Compute impact only if this is a comparison with both results."""
    if not reform_sim:
        return None
    if not baseline_result or not reform_result:
        return None

    household = session.get(Household, baseline_sim.household_id)
    if not household:
        return None

    config = get_country_config(household.tax_benefit_model_name)
    return compute_household_impact(baseline_result, reform_result, config)


# =============================================================================
# Validation Helpers
# =============================================================================


def validate_household_exists(household_id: UUID, session: Session) -> Household:
    """Validate household exists and return it."""
    household = session.get(Household, household_id)
    if not household:
        raise HTTPException(
            status_code=404,
            detail=f"Household {household_id} not found",
        )
    return household


def validate_policy_exists(policy_id: UUID | None, session: Session) -> None:
    """Validate policy exists if provided."""
    if not policy_id:
        return

    policy = session.get(Policy, policy_id)
    if not policy:
        raise HTTPException(
            status_code=404,
            detail=f"Policy {policy_id} not found",
        )


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/household-impact", response_model=HouseholdImpactResponse)
def household_impact(
    request: HouseholdImpactRequest,
    session: Session = Depends(get_session),
) -> HouseholdImpactResponse:
    """Run household impact analysis.

    If policy_id is None: single run under current law.
    If policy_id is set: comparison (baseline vs reform).

    This is an async operation. The endpoint returns immediately with a report_id
    and status="pending". Poll GET /analysis/household-impact/{report_id} until
    status="completed" to get results.
    """
    household = validate_household_exists(request.household_id, session)
    validate_policy_exists(request.policy_id, session)

    model_version = _get_model_version(household.tax_benefit_model_name, session)

    baseline_sim = _create_baseline_simulation(
        household, model_version.id, request.dynamic_id, session
    )
    reform_sim = _create_reform_simulation(
        household, model_version.id, request.policy_id, request.dynamic_id, session
    )

    report_type = "household_comparison" if request.policy_id else "household_single"
    report = _get_or_create_report(
        baseline_sim_id=baseline_sim.id,
        reform_sim_id=reform_sim.id if reform_sim else None,
        label=f"Household impact: {household.tax_benefit_model_name}",
        report_type=report_type,
        session=session,
    )

    if report.status == ReportStatus.PENDING:
        with logfire.span("trigger_household_impact", job_id=str(report.id)):
            _trigger_household_impact(
                str(report.id), household.tax_benefit_model_name, session
            )

    return build_household_response(report, baseline_sim, reform_sim, session)


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
            status_code=500,
            detail="Report missing baseline simulation ID",
        )

    baseline_sim = session.get(Simulation, report.baseline_simulation_id)
    if not baseline_sim:
        raise HTTPException(status_code=500, detail="Baseline simulation data missing")

    reform_sim = None
    if report.reform_simulation_id:
        reform_sim = session.get(Simulation, report.reform_simulation_id)

    return build_household_response(report, baseline_sim, reform_sim, session)


# =============================================================================
# Simulation Creation Helpers
# =============================================================================


def _create_baseline_simulation(
    household: Household,
    model_version_id: UUID,
    dynamic_id: UUID | None,
    session: Session,
) -> Simulation:
    """Create baseline simulation (current law, no policy)."""
    return _get_or_create_simulation(
        simulation_type=SimulationType.HOUSEHOLD,
        model_version_id=model_version_id,
        policy_id=None,
        dynamic_id=dynamic_id,
        session=session,
        household_id=household.id,
    )


def _create_reform_simulation(
    household: Household,
    model_version_id: UUID,
    policy_id: UUID | None,
    dynamic_id: UUID | None,
    session: Session,
) -> Simulation | None:
    """Create reform simulation if policy_id is provided."""
    if not policy_id:
        return None

    return _get_or_create_simulation(
        simulation_type=SimulationType.HOUSEHOLD,
        model_version_id=model_version_id,
        policy_id=policy_id,
        dynamic_id=dynamic_id,
        session=session,
        household_id=household.id,
    )
