"""Household calculation endpoints.

These endpoints are async - they create jobs that are processed by Modal functions.
Poll the status endpoint until the job is complete.
"""

from typing import Any, Literal
from uuid import UUID

import logfire
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from policyengine_api.models import (
    Dynamic,
    HouseholdJob,
    HouseholdJobStatus,
    Policy,
)
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/household", tags=["household"])


class HouseholdCalculateRequest(BaseModel):
    """Request body for household calculation.

    IMPORTANT: Use flat values for variables, NOT time-period dictionaries.
    The year is specified separately via the `year` parameter.

    CORRECT: {"employment_income": 70000, "age": 40}
    WRONG: {"employment_income": {"2024": 70000}, "age": {"2024": 40}}

    Example US request:
    {
        "tax_benefit_model_name": "policyengine_us",
        "people": [{"employment_income": 70000, "age": 40}],
        "tax_unit": {"state_code": "CA"},
        "household": {"state_fips": 6},
        "year": 2024
    }

    Example UK request:
    {
        "tax_benefit_model_name": "policyengine_uk",
        "people": [{"employment_income": 50000, "age": 30}],
        "household": {},
        "year": 2026
    }
    """

    tax_benefit_model_name: Literal["policyengine_uk", "policyengine_us"] = Field(
        description="Which country model to use"
    )
    people: list[dict[str, Any]] = Field(
        description="List of people with flat variable values (e.g. [{'age': 30, 'employment_income': 50000}]). Do NOT use time-period format."
    )
    benunit: dict[str, Any] = Field(
        default_factory=dict, description="UK benefit unit variables (flat values)"
    )
    marital_unit: dict[str, Any] = Field(
        default_factory=dict, description="US marital unit variables (flat values)"
    )
    family: dict[str, Any] = Field(
        default_factory=dict, description="US family variables (flat values)"
    )
    spm_unit: dict[str, Any] = Field(
        default_factory=dict, description="US SPM unit variables (flat values)"
    )
    tax_unit: dict[str, Any] = Field(
        default_factory=dict,
        description="US tax unit variables (flat values, e.g. {'state_code': 'CA'})",
    )
    household: dict[str, Any] = Field(
        default_factory=dict,
        description="Household variables (flat values, e.g. {'state_fips': 6} for US)",
    )
    year: int | None = Field(
        default=None,
        description="Simulation year (default: 2024 for US, 2026 for UK). Specify this instead of embedding years in variable values.",
    )
    policy_id: UUID | None = Field(
        default=None, description="Optional policy reform ID"
    )
    dynamic_id: UUID | None = Field(
        default=None, description="Optional behavioural response ID"
    )


class HouseholdCalculateResponse(BaseModel):
    """Response from household calculation."""

    person: list[dict[str, Any]]
    benunit: list[dict[str, Any]] | None = None
    marital_unit: list[dict[str, Any]] | None = None
    family: list[dict[str, Any]] | None = None
    spm_unit: list[dict[str, Any]] | None = None
    tax_unit: list[dict[str, Any]] | None = None
    household: dict[str, Any]


class HouseholdJobResponse(BaseModel):
    """Response from creating a household job."""

    job_id: UUID
    status: HouseholdJobStatus


class HouseholdJobStatusResponse(BaseModel):
    """Response from polling a household job."""

    job_id: UUID
    status: HouseholdJobStatus
    result: HouseholdCalculateResponse | None = None
    error_message: str | None = None


class HouseholdImpactRequest(BaseModel):
    """Request body for household impact comparison.

    Same format as HouseholdCalculateRequest - use flat values, NOT time-period dictionaries.

    Example:
    {
        "tax_benefit_model_name": "policyengine_us",
        "people": [{"employment_income": 70000, "age": 40}],
        "tax_unit": {"state_code": "CA"},
        "household": {"state_fips": 6},
        "year": 2024,
        "policy_id": "uuid-of-reform-policy"
    }
    """

    tax_benefit_model_name: Literal["policyengine_uk", "policyengine_us"] = Field(
        description="Which country model to use"
    )
    people: list[dict[str, Any]] = Field(
        description="List of people with flat variable values. Do NOT use time-period format."
    )
    benunit: dict[str, Any] = Field(
        default_factory=dict, description="UK benefit unit variables (flat values)"
    )
    marital_unit: dict[str, Any] = Field(
        default_factory=dict, description="US marital unit variables (flat values)"
    )
    family: dict[str, Any] = Field(
        default_factory=dict, description="US family variables (flat values)"
    )
    spm_unit: dict[str, Any] = Field(
        default_factory=dict, description="US SPM unit variables (flat values)"
    )
    tax_unit: dict[str, Any] = Field(
        default_factory=dict, description="US tax unit variables (flat values)"
    )
    household: dict[str, Any] = Field(
        default_factory=dict, description="Household variables (flat values)"
    )
    year: int | None = Field(
        default=None, description="Simulation year (default: 2024 for US, 2026 for UK)"
    )
    policy_id: UUID | None = Field(
        default=None, description="Reform policy ID to compare against baseline"
    )
    dynamic_id: UUID | None = Field(
        default=None, description="Optional behavioural response ID"
    )


class HouseholdImpactResponse(BaseModel):
    """Response from household impact comparison."""

    baseline: HouseholdCalculateResponse
    reform: HouseholdCalculateResponse
    impact: dict[str, Any]  # Computed differences


class HouseholdImpactJobStatusResponse(BaseModel):
    """Response from polling a household impact job."""

    job_id: UUID
    status: HouseholdJobStatus
    baseline_result: HouseholdCalculateResponse | None = None
    reform_result: HouseholdCalculateResponse | None = None
    impact: dict[str, Any] | None = None
    error_message: str | None = None


def _run_local_household_uk(
    job_id: str,
    people: list[dict],
    benunit: dict,
    household: dict,
    year: int,
    policy_data: dict | None,
    session: Session,
) -> None:
    """Run UK household calculation locally."""
    from datetime import datetime, timezone

    from policyengine.tax_benefit_models.uk import uk_latest
    from policyengine.tax_benefit_models.uk.analysis import (
        UKHouseholdInput,
        calculate_household_impact,
    )

    try:
        # Build policy if provided
        policy = None
        if policy_data:
            from policyengine.core.policy import ParameterValue as PEParameterValue
            from policyengine.core.policy import Policy as PEPolicy

            pe_param_values = []
            param_lookup = {p.name: p for p in uk_latest.parameters}
            for pv in policy_data.get("parameter_values", []):
                pe_param = param_lookup.get(pv["parameter_name"])
                if pe_param:
                    pe_pv = PEParameterValue(
                        parameter=pe_param,
                        value=pv["value"],
                        start_date=datetime.fromisoformat(pv["start_date"])
                        if pv.get("start_date")
                        else None,
                        end_date=datetime.fromisoformat(pv["end_date"])
                        if pv.get("end_date")
                        else None,
                    )
                    pe_param_values.append(pe_pv)
            policy = PEPolicy(
                name=policy_data.get("name", ""),
                description=policy_data.get("description", ""),
                parameter_values=pe_param_values,
            )

        pe_input = UKHouseholdInput(
            people=people,
            benunit=benunit,
            household=household,
            year=year,
        )

        result = calculate_household_impact(pe_input, policy=policy)

        # Update job with result
        job = session.get(HouseholdJob, job_id)
        if job:
            job.status = HouseholdJobStatus.COMPLETED
            job.result = {
                "person": result.person,
                "benunit": result.benunit,
                "household": result.household,
            }
            job.completed_at = datetime.now(timezone.utc)
            session.add(job)
            session.commit()

    except Exception as e:
        from datetime import datetime, timezone

        # Update job with error
        job = session.get(HouseholdJob, job_id)
        if job:
            job.status = HouseholdJobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            session.add(job)
            session.commit()
        raise


def _run_local_household_us(
    job_id: str,
    people: list[dict],
    marital_unit: dict,
    family: dict,
    spm_unit: dict,
    tax_unit: dict,
    household: dict,
    year: int,
    policy_data: dict | None,
    session: Session,
) -> None:
    """Run US household calculation locally."""
    from datetime import datetime, timezone

    from policyengine.tax_benefit_models.us import us_latest
    from policyengine.tax_benefit_models.us.analysis import (
        USHouseholdInput,
        calculate_household_impact,
    )

    try:
        # Build policy if provided
        policy = None
        if policy_data:
            from policyengine.core.policy import ParameterValue as PEParameterValue
            from policyengine.core.policy import Policy as PEPolicy

            pe_param_values = []
            param_lookup = {p.name: p for p in us_latest.parameters}
            for pv in policy_data.get("parameter_values", []):
                pe_param = param_lookup.get(pv["parameter_name"])
                if pe_param:
                    pe_pv = PEParameterValue(
                        parameter=pe_param,
                        value=pv["value"],
                        start_date=datetime.fromisoformat(pv["start_date"])
                        if pv.get("start_date")
                        else None,
                        end_date=datetime.fromisoformat(pv["end_date"])
                        if pv.get("end_date")
                        else None,
                    )
                    pe_param_values.append(pe_pv)
            policy = PEPolicy(
                name=policy_data.get("name", ""),
                description=policy_data.get("description", ""),
                parameter_values=pe_param_values,
            )

        pe_input = USHouseholdInput(
            people=people,
            marital_unit=marital_unit,
            family=family,
            spm_unit=spm_unit,
            tax_unit=tax_unit,
            household=household,
            year=year,
        )

        result = calculate_household_impact(pe_input, policy=policy)

        # Update job with result
        job = session.get(HouseholdJob, job_id)
        if job:
            job.status = HouseholdJobStatus.COMPLETED
            job.result = {
                "person": result.person,
                "marital_unit": result.marital_unit,
                "family": result.family,
                "spm_unit": result.spm_unit,
                "tax_unit": result.tax_unit,
                "household": result.household,
            }
            job.completed_at = datetime.now(timezone.utc)
            session.add(job)
            session.commit()

    except Exception as e:
        from datetime import datetime, timezone

        # Update job with error
        job = session.get(HouseholdJob, job_id)
        if job:
            job.status = HouseholdJobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            session.add(job)
            session.commit()
        raise


def _trigger_modal_household(
    job_id: str,
    request: HouseholdCalculateRequest,
    policy_data: dict | None,
    dynamic_data: dict | None,
    session: Session | None = None,
) -> None:
    """Trigger household simulation - Modal or local based on settings."""
    from policyengine_api.config import settings

    if not settings.demo_use_modal and session is not None:
        # Run locally
        if request.tax_benefit_model_name == "policyengine_uk":
            _run_local_household_uk(
                job_id=job_id,
                people=request.people,
                benunit=request.benunit,
                household=request.household,
                year=request.year or 2026,
                policy_data=policy_data,
                session=session,
            )
        else:
            _run_local_household_us(
                job_id=job_id,
                people=request.people,
                marital_unit=request.marital_unit,
                family=request.family,
                spm_unit=request.spm_unit,
                tax_unit=request.tax_unit,
                household=request.household,
                year=request.year or 2024,
                policy_data=policy_data,
                session=session,
            )
    else:
        # Use Modal
        import modal

        if request.tax_benefit_model_name == "policyengine_uk":
            fn = modal.Function.from_name("policyengine", "simulate_household_uk")
            fn.spawn(
                job_id=job_id,
                people=request.people,
                benunit=request.benunit,
                household=request.household,
                year=request.year or 2026,
                policy_data=policy_data,
                dynamic_data=dynamic_data,
            )
        else:
            fn = modal.Function.from_name("policyengine", "simulate_household_us")
            fn.spawn(
                job_id=job_id,
                people=request.people,
                marital_unit=request.marital_unit,
                family=request.family,
                spm_unit=request.spm_unit,
                tax_unit=request.tax_unit,
                household=request.household,
                year=request.year or 2024,
                policy_data=policy_data,
                dynamic_data=dynamic_data,
            )


def _get_policy_data(policy_id: UUID | None, session: Session) -> dict | None:
    """Get policy data for Modal function."""
    if policy_id is None:
        return None

    db_policy = session.get(Policy, policy_id)
    if not db_policy:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

    return {
        "name": db_policy.name,
        "description": db_policy.description,
        "parameter_values": [
            {
                "parameter_name": pv.parameter.name if pv.parameter else None,
                "value": pv.value_json.get("value")
                if isinstance(pv.value_json, dict)
                else pv.value_json,
                "start_date": pv.start_date.isoformat() if pv.start_date else None,
                "end_date": pv.end_date.isoformat() if pv.end_date else None,
            }
            for pv in db_policy.parameter_values
            if pv.parameter
        ],
    }


def _get_dynamic_data(dynamic_id: UUID | None, session: Session) -> dict | None:
    """Get dynamic data for Modal function."""
    if dynamic_id is None:
        return None

    db_dynamic = session.get(Dynamic, dynamic_id)
    if not db_dynamic:
        raise HTTPException(status_code=404, detail=f"Dynamic {dynamic_id} not found")

    return {
        "name": db_dynamic.name,
        "description": db_dynamic.description,
        "parameter_values": [
            {
                "parameter_name": pv.parameter.name if pv.parameter else None,
                "value": pv.value_json.get("value")
                if isinstance(pv.value_json, dict)
                else pv.value_json,
                "start_date": pv.start_date.isoformat() if pv.start_date else None,
                "end_date": pv.end_date.isoformat() if pv.end_date else None,
            }
            for pv in db_dynamic.parameter_values
            if pv.parameter
        ],
    }


@router.post("/calculate", response_model=HouseholdJobResponse)
def calculate_household(
    request: HouseholdCalculateRequest,
    session: Session = Depends(get_session),
) -> HouseholdJobResponse:
    """Create a household calculation job.

    This is an async operation. The endpoint returns immediately with a job_id.
    Poll GET /household/calculate/{job_id} until status is "completed" to get results.

    Use flat values for all variables - do NOT use time-period format like {"2024": value}.
    The simulation year is specified via the `year` parameter.

    US example: people=[{"employment_income": 70000, "age": 40}], tax_unit={"state_code": "CA"}, year=2024
    UK example: people=[{"employment_income": 50000, "age": 30}], year=2026
    """
    with logfire.span(
        "create_household_job",
        model=request.tax_benefit_model_name,
        num_people=len(request.people),
        year=request.year,
        has_policy=request.policy_id is not None,
        has_dynamic=request.dynamic_id is not None,
    ):
        # Get policy and dynamic data for Modal
        policy_data = _get_policy_data(request.policy_id, session)
        dynamic_data = _get_dynamic_data(request.dynamic_id, session)

        # Create job record
        job = HouseholdJob(
            tax_benefit_model_name=request.tax_benefit_model_name,
            request_data={
                "people": request.people,
                "benunit": request.benunit,
                "marital_unit": request.marital_unit,
                "family": request.family,
                "spm_unit": request.spm_unit,
                "tax_unit": request.tax_unit,
                "household": request.household,
                "year": request.year,
            },
            policy_id=request.policy_id,
            dynamic_id=request.dynamic_id,
            status=HouseholdJobStatus.PENDING,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        # Trigger calculation (Modal or local based on settings)
        with logfire.span("trigger_calculation", job_id=str(job.id)):
            _trigger_modal_household(
                str(job.id),
                request,
                policy_data,
                dynamic_data,
                session=session,
            )

        return HouseholdJobResponse(
            job_id=job.id,
            status=job.status,
        )


@router.get("/calculate/{job_id}", response_model=HouseholdJobStatusResponse)
def get_household_job_status(
    job_id: UUID,
    session: Session = Depends(get_session),
) -> HouseholdJobStatusResponse:
    """Get the status and result of a household calculation job."""
    job = session.get(HouseholdJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    result = None
    if job.status == HouseholdJobStatus.COMPLETED and job.result:
        result = HouseholdCalculateResponse(
            person=job.result.get("person", []),
            benunit=job.result.get("benunit"),
            marital_unit=job.result.get("marital_unit"),
            family=job.result.get("family"),
            spm_unit=job.result.get("spm_unit"),
            tax_unit=job.result.get("tax_unit"),
            household=job.result.get("household", {}),
        )

    return HouseholdJobStatusResponse(
        job_id=job.id,
        status=job.status,
        result=result,
        error_message=job.error_message,
    )


def _compute_impact(
    baseline: HouseholdCalculateResponse, reform: HouseholdCalculateResponse
) -> dict[str, Any]:
    """Compute difference between baseline and reform."""
    impact = {}

    # Compute household-level differences
    hh_impact = {}
    for key in baseline.household:
        if key in reform.household:
            baseline_val = baseline.household[key]
            reform_val = reform.household[key]
            if isinstance(baseline_val, (int, float)) and isinstance(
                reform_val, (int, float)
            ):
                hh_impact[key] = {
                    "baseline": baseline_val,
                    "reform": reform_val,
                    "change": reform_val - baseline_val,
                }
    impact["household"] = hh_impact

    # Compute person-level differences
    person_impact = []
    for i, (bp, rp) in enumerate(zip(baseline.person, reform.person)):
        person_diff = {}
        for key in bp:
            if key in rp:
                baseline_val = bp[key]
                reform_val = rp[key]
                if isinstance(baseline_val, (int, float)) and isinstance(
                    reform_val, (int, float)
                ):
                    person_diff[key] = {
                        "baseline": baseline_val,
                        "reform": reform_val,
                        "change": reform_val - baseline_val,
                    }
        person_impact.append(person_diff)
    impact["person"] = person_impact

    return impact


@router.post("/impact", response_model=HouseholdJobResponse)
def calculate_household_impact_comparison(
    request: HouseholdImpactRequest,
    session: Session = Depends(get_session),
) -> HouseholdJobResponse:
    """Create a household impact comparison job.

    This is an async operation. The endpoint returns immediately with a job_id.
    Poll GET /household/impact/{job_id} until status is "completed" to get results.

    Compares the household under baseline (current law) vs reform (policy_id).
    Returns both calculations plus computed differences.

    Use flat values for all variables - do NOT use time-period format like {"2024": value}.
    """
    with logfire.span(
        "create_household_impact_job",
        model=request.tax_benefit_model_name,
        num_people=len(request.people),
        year=request.year,
        has_policy=request.policy_id is not None,
    ):
        # Get policy and dynamic data
        policy_data = _get_policy_data(request.policy_id, session)
        dynamic_data = _get_dynamic_data(request.dynamic_id, session)

        # Create baseline job (no policy)
        baseline_job = HouseholdJob(
            tax_benefit_model_name=request.tax_benefit_model_name,
            request_data={
                "people": request.people,
                "benunit": request.benunit,
                "marital_unit": request.marital_unit,
                "family": request.family,
                "spm_unit": request.spm_unit,
                "tax_unit": request.tax_unit,
                "household": request.household,
                "year": request.year,
                "is_impact_baseline": True,
            },
            policy_id=None,
            dynamic_id=request.dynamic_id,
            status=HouseholdJobStatus.PENDING,
        )
        session.add(baseline_job)

        # Create reform job (with policy)
        reform_job = HouseholdJob(
            tax_benefit_model_name=request.tax_benefit_model_name,
            request_data={
                "people": request.people,
                "benunit": request.benunit,
                "marital_unit": request.marital_unit,
                "family": request.family,
                "spm_unit": request.spm_unit,
                "tax_unit": request.tax_unit,
                "household": request.household,
                "year": request.year,
                "is_impact_reform": True,
                "baseline_job_id": None,  # Will update after commit
            },
            policy_id=request.policy_id,
            dynamic_id=request.dynamic_id,
            status=HouseholdJobStatus.PENDING,
        )
        session.add(reform_job)
        session.commit()
        session.refresh(baseline_job)
        session.refresh(reform_job)

        # Update reform job with baseline reference
        reform_job.request_data["baseline_job_id"] = str(baseline_job.id)
        session.add(reform_job)
        session.commit()

        # Trigger Modal functions for both
        baseline_request = HouseholdCalculateRequest(
            tax_benefit_model_name=request.tax_benefit_model_name,
            people=request.people,
            benunit=request.benunit,
            marital_unit=request.marital_unit,
            family=request.family,
            spm_unit=request.spm_unit,
            tax_unit=request.tax_unit,
            household=request.household,
            year=request.year,
            policy_id=None,
            dynamic_id=request.dynamic_id,
        )
        reform_request = HouseholdCalculateRequest(
            tax_benefit_model_name=request.tax_benefit_model_name,
            people=request.people,
            benunit=request.benunit,
            marital_unit=request.marital_unit,
            family=request.family,
            spm_unit=request.spm_unit,
            tax_unit=request.tax_unit,
            household=request.household,
            year=request.year,
            policy_id=request.policy_id,
            dynamic_id=request.dynamic_id,
        )

        with logfire.span("trigger_baseline", job_id=str(baseline_job.id)):
            _trigger_modal_household(
                str(baseline_job.id),
                baseline_request,
                None,
                dynamic_data,
                session=session,
            )

        with logfire.span("trigger_reform", job_id=str(reform_job.id)):
            _trigger_modal_household(
                str(reform_job.id),
                reform_request,
                policy_data,
                dynamic_data,
                session=session,
            )

        # Return the reform job id (client polls this)
        return HouseholdJobResponse(
            job_id=reform_job.id,
            status=reform_job.status,
        )


@router.get("/impact/{job_id}", response_model=HouseholdImpactJobStatusResponse)
def get_household_impact_job_status(
    job_id: UUID,
    session: Session = Depends(get_session),
) -> HouseholdImpactJobStatusResponse:
    """Get the status and result of a household impact comparison job."""
    reform_job = session.get(HouseholdJob, job_id)
    if not reform_job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Get baseline job id from request data
    baseline_job_id = reform_job.request_data.get("baseline_job_id")
    if not baseline_job_id:
        # This is not an impact job, just a regular calculation
        raise HTTPException(
            status_code=400,
            detail="This is not an impact job. Use GET /household/calculate/{job_id} instead.",
        )

    baseline_job = session.get(HouseholdJob, UUID(baseline_job_id))
    if not baseline_job:
        raise HTTPException(status_code=500, detail="Baseline job not found")

    # Determine overall status
    if baseline_job.status == HouseholdJobStatus.FAILED:
        overall_status = HouseholdJobStatus.FAILED
        error_message = f"Baseline calculation failed: {baseline_job.error_message}"
    elif reform_job.status == HouseholdJobStatus.FAILED:
        overall_status = HouseholdJobStatus.FAILED
        error_message = f"Reform calculation failed: {reform_job.error_message}"
    elif (
        baseline_job.status == HouseholdJobStatus.COMPLETED
        and reform_job.status == HouseholdJobStatus.COMPLETED
    ):
        overall_status = HouseholdJobStatus.COMPLETED
        error_message = None
    elif (
        baseline_job.status == HouseholdJobStatus.RUNNING
        or reform_job.status == HouseholdJobStatus.RUNNING
    ):
        overall_status = HouseholdJobStatus.RUNNING
        error_message = None
    else:
        overall_status = HouseholdJobStatus.PENDING
        error_message = None

    baseline_result = None
    reform_result = None
    impact = None

    if overall_status == HouseholdJobStatus.COMPLETED:
        baseline_result = HouseholdCalculateResponse(
            person=baseline_job.result.get("person", []),
            benunit=baseline_job.result.get("benunit"),
            marital_unit=baseline_job.result.get("marital_unit"),
            family=baseline_job.result.get("family"),
            spm_unit=baseline_job.result.get("spm_unit"),
            tax_unit=baseline_job.result.get("tax_unit"),
            household=baseline_job.result.get("household", {}),
        )
        reform_result = HouseholdCalculateResponse(
            person=reform_job.result.get("person", []),
            benunit=reform_job.result.get("benunit"),
            marital_unit=reform_job.result.get("marital_unit"),
            family=reform_job.result.get("family"),
            spm_unit=reform_job.result.get("spm_unit"),
            tax_unit=reform_job.result.get("tax_unit"),
            household=reform_job.result.get("household", {}),
        )
        impact = _compute_impact(baseline_result, reform_result)

    return HouseholdImpactJobStatusResponse(
        job_id=reform_job.id,
        status=overall_status,
        baseline_result=baseline_result,
        reform_result=reform_result,
        impact=impact,
        error_message=error_message,
    )
