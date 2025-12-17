"""Household calculation endpoints."""

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from policyengine_api.models import Dynamic, Policy
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/household", tags=["household"])


class HouseholdCalculateRequest(BaseModel):
    """Request body for household calculation."""

    tax_benefit_model_name: Literal["policyengine_uk", "policyengine_us"]
    people: list[dict[str, Any]]
    benunit: dict[str, Any] = Field(default_factory=dict)
    marital_unit: dict[str, Any] = Field(default_factory=dict)
    family: dict[str, Any] = Field(default_factory=dict)
    spm_unit: dict[str, Any] = Field(default_factory=dict)
    tax_unit: dict[str, Any] = Field(default_factory=dict)
    household: dict[str, Any] = Field(default_factory=dict)
    year: int | None = None
    policy_id: UUID | None = None
    dynamic_id: UUID | None = None


class HouseholdCalculateResponse(BaseModel):
    """Response from household calculation."""

    person: list[dict[str, Any]]
    benunit: list[dict[str, Any]] | None = None
    marital_unit: list[dict[str, Any]] | None = None
    family: list[dict[str, Any]] | None = None
    spm_unit: list[dict[str, Any]] | None = None
    tax_unit: list[dict[str, Any]] | None = None
    household: dict[str, Any]


class HouseholdImpactRequest(BaseModel):
    """Request body for household impact comparison."""

    tax_benefit_model_name: Literal["policyengine_uk", "policyengine_us"]
    people: list[dict[str, Any]]
    benunit: dict[str, Any] = Field(default_factory=dict)
    marital_unit: dict[str, Any] = Field(default_factory=dict)
    family: dict[str, Any] = Field(default_factory=dict)
    spm_unit: dict[str, Any] = Field(default_factory=dict)
    tax_unit: dict[str, Any] = Field(default_factory=dict)
    household: dict[str, Any] = Field(default_factory=dict)
    year: int | None = None
    policy_id: UUID | None = None  # Reform policy (baseline uses no policy)
    dynamic_id: UUID | None = None


class HouseholdImpactResponse(BaseModel):
    """Response from household impact comparison."""

    baseline: HouseholdCalculateResponse
    reform: HouseholdCalculateResponse
    impact: dict[str, Any]  # Computed differences


def _get_pe_policy(policy_id: UUID | None, model_version, session: Session):
    """Convert database Policy to policyengine Policy."""
    if policy_id is None:
        return None

    from policyengine.core.policy import ParameterValue as PEParameterValue
    from policyengine.core.policy import Policy as PEPolicy

    db_policy = session.get(Policy, policy_id)
    if not db_policy:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

    # Build param lookup from model version
    param_lookup = {p.name: p for p in model_version.parameters}

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


def _get_pe_dynamic(dynamic_id: UUID | None, model_version, session: Session):
    """Convert database Dynamic to policyengine Dynamic."""
    if dynamic_id is None:
        return None

    from policyengine.core.dynamic import Dynamic as PEDynamic
    from policyengine.core.policy import ParameterValue as PEParameterValue

    db_dynamic = session.get(Dynamic, dynamic_id)
    if not db_dynamic:
        raise HTTPException(status_code=404, detail=f"Dynamic {dynamic_id} not found")

    # Build param lookup from model version
    param_lookup = {p.name: p for p in model_version.parameters}

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


@router.post("/calculate", response_model=HouseholdCalculateResponse)
def calculate_household(
    request: HouseholdCalculateRequest,
    session: Session = Depends(get_session),
) -> HouseholdCalculateResponse:
    """Calculate tax and benefit impacts for a household."""
    if request.tax_benefit_model_name == "policyengine_uk":
        from policyengine.tax_benefit_models.uk import uk_latest

        pe_model_version = uk_latest
    else:
        from policyengine.tax_benefit_models.us import us_latest

        pe_model_version = us_latest

    policy = _get_pe_policy(request.policy_id, pe_model_version, session)
    dynamic = _get_pe_dynamic(request.dynamic_id, pe_model_version, session)

    if request.tax_benefit_model_name == "policyengine_uk":
        return _calculate_uk(request, policy, dynamic)
    elif request.tax_benefit_model_name == "policyengine_us":
        return _calculate_us(request, policy, dynamic)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported model: {request.tax_benefit_model_name}",
        )


def _calculate_uk(
    request: HouseholdCalculateRequest, policy, dynamic
) -> HouseholdCalculateResponse:
    """Calculate for UK."""
    from policyengine.tax_benefit_models.uk.analysis import (
        UKHouseholdInput,
        calculate_household_impact,
    )

    pe_input = UKHouseholdInput(
        people=request.people,
        benunit=request.benunit,
        household=request.household,
        year=request.year or 2026,
    )

    result = calculate_household_impact(pe_input, policy=policy)

    return HouseholdCalculateResponse(
        person=result.person,
        benunit=result.benunit,
        household=result.household,
    )


def _calculate_us(
    request: HouseholdCalculateRequest, policy, dynamic
) -> HouseholdCalculateResponse:
    """Calculate for US."""
    from policyengine.tax_benefit_models.us.analysis import (
        USHouseholdInput,
        calculate_household_impact,
    )

    pe_input = USHouseholdInput(
        people=request.people,
        marital_unit=request.marital_unit,
        family=request.family,
        spm_unit=request.spm_unit,
        tax_unit=request.tax_unit,
        household=request.household,
        year=request.year or 2024,
    )

    result = calculate_household_impact(pe_input, policy=policy)

    return HouseholdCalculateResponse(
        person=result.person,
        marital_unit=result.marital_unit,
        family=result.family,
        spm_unit=result.spm_unit,
        tax_unit=result.tax_unit,
        household=result.household,
    )


def _compute_impact(baseline: HouseholdCalculateResponse, reform: HouseholdCalculateResponse) -> dict[str, Any]:
    """Compute difference between baseline and reform."""
    impact = {}

    # Compute household-level differences
    hh_impact = {}
    for key in baseline.household:
        if key in reform.household:
            baseline_val = baseline.household[key]
            reform_val = reform.household[key]
            if isinstance(baseline_val, (int, float)) and isinstance(reform_val, (int, float)):
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
                if isinstance(baseline_val, (int, float)) and isinstance(reform_val, (int, float)):
                    person_diff[key] = {
                        "baseline": baseline_val,
                        "reform": reform_val,
                        "change": reform_val - baseline_val,
                    }
        person_impact.append(person_diff)
    impact["person"] = person_impact

    return impact


@router.post("/impact", response_model=HouseholdImpactResponse)
def calculate_household_impact_comparison(
    request: HouseholdImpactRequest,
    session: Session = Depends(get_session),
) -> HouseholdImpactResponse:
    """Calculate the impact of a policy reform on a household.

    Compares the household under baseline (current law) vs reform (policy_id).
    Returns both calculations plus computed differences.
    """
    # Build baseline request (no policy)
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

    # Build reform request (with policy)
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

    # Calculate both
    baseline = calculate_household(baseline_request, session)
    reform = calculate_household(reform_request, session)

    # Compute impact
    impact = _compute_impact(baseline, reform)

    return HouseholdImpactResponse(
        baseline=baseline,
        reform=reform,
        impact=impact,
    )
