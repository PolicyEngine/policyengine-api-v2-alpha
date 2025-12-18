"""Household calculation endpoints."""

from typing import Any, Literal
from uuid import UUID

import logfire
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from policyengine_api.models import Dynamic, Policy
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


def _get_pe_policy(policy_id: UUID | None, model_version, session: Session):
    """Convert database Policy to policyengine Policy."""
    if policy_id is None:
        return None

    with logfire.span("load_policy_from_db", policy_id=str(policy_id)):
        from policyengine.core.policy import ParameterValue as PEParameterValue
        from policyengine.core.policy import Policy as PEPolicy

        db_policy = session.get(Policy, policy_id)
        if not db_policy:
            raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")

        # Build param lookup from model version
        with logfire.span("build_param_lookup"):
            param_lookup = {p.name: p for p in model_version.parameters}

        with logfire.span(
            "build_policy_param_values", num_values=len(db_policy.parameter_values)
        ):
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

    with logfire.span("load_dynamic_from_db", dynamic_id=str(dynamic_id)):
        from policyengine.core.dynamic import Dynamic as PEDynamic
        from policyengine.core.policy import ParameterValue as PEParameterValue

        db_dynamic = session.get(Dynamic, dynamic_id)
        if not db_dynamic:
            raise HTTPException(
                status_code=404, detail=f"Dynamic {dynamic_id} not found"
            )

        # Build param lookup from model version
        with logfire.span("build_param_lookup"):
            param_lookup = {p.name: p for p in model_version.parameters}

        with logfire.span(
            "build_dynamic_param_values", num_values=len(db_dynamic.parameter_values)
        ):
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
    """Calculate tax and benefit impacts for a household.

    Use flat values for all variables - do NOT use time-period format like {"2024": value}.
    The simulation year is specified via the `year` parameter.

    US example: people=[{"employment_income": 70000, "age": 40}], tax_unit={"state_code": "CA"}, year=2024
    UK example: people=[{"employment_income": 50000, "age": 30}], year=2026
    """
    with logfire.span(
        "calculate_household",
        model=request.tax_benefit_model_name,
        num_people=len(request.people),
        year=request.year,
        has_policy=request.policy_id is not None,
        has_dynamic=request.dynamic_id is not None,
    ):
        with logfire.span("load_model", model=request.tax_benefit_model_name):
            if request.tax_benefit_model_name == "policyengine_uk":
                from policyengine.tax_benefit_models.uk import uk_latest

                pe_model_version = uk_latest
            else:
                from policyengine.tax_benefit_models.us import us_latest

                pe_model_version = us_latest

        with logfire.span("load_policy_and_dynamic"):
            policy = _get_pe_policy(request.policy_id, pe_model_version, session)
            dynamic = _get_pe_dynamic(request.dynamic_id, pe_model_version, session)

        with logfire.span("run_calculation", model=request.tax_benefit_model_name):
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
    with logfire.span("import_uk_analysis"):
        from policyengine.tax_benefit_models.uk.analysis import (
            UKHouseholdInput,
            calculate_household_impact,
        )

    with logfire.span("build_uk_input", num_people=len(request.people)):
        pe_input = UKHouseholdInput(
            people=request.people,
            benunit=request.benunit,
            household=request.household,
            year=request.year or 2026,
        )

    with logfire.span("calculate_uk_household_impact", has_policy=policy is not None):
        result = calculate_household_impact(pe_input, policy=policy)

    with logfire.span("build_uk_response"):
        return HouseholdCalculateResponse(
            person=result.person,
            benunit=result.benunit,
            household=result.household,
        )


def _calculate_us(
    request: HouseholdCalculateRequest, policy, dynamic
) -> HouseholdCalculateResponse:
    """Calculate for US."""
    with logfire.span("import_us_analysis"):
        from policyengine.tax_benefit_models.us.analysis import (
            USHouseholdInput,
            calculate_household_impact,
        )

    with logfire.span("build_us_input", num_people=len(request.people)):
        pe_input = USHouseholdInput(
            people=request.people,
            marital_unit=request.marital_unit,
            family=request.family,
            spm_unit=request.spm_unit,
            tax_unit=request.tax_unit,
            household=request.household,
            year=request.year or 2024,
        )

    with logfire.span("calculate_us_household_impact", has_policy=policy is not None):
        result = calculate_household_impact(pe_input, policy=policy)

    with logfire.span("build_us_response"):
        return HouseholdCalculateResponse(
            person=result.person,
            marital_unit=result.marital_unit,
            family=result.family,
            spm_unit=result.spm_unit,
            tax_unit=result.tax_unit,
            household=result.household,
        )


def _compute_impact(
    baseline: HouseholdCalculateResponse, reform: HouseholdCalculateResponse
) -> dict[str, Any]:
    """Compute difference between baseline and reform."""
    with logfire.span("compute_impact_diff", num_people=len(baseline.person)):
        impact = {}

        # Compute household-level differences
        with logfire.span("compute_household_diff"):
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
        with logfire.span("compute_person_diff"):
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


@router.post("/impact", response_model=HouseholdImpactResponse)
def calculate_household_impact_comparison(
    request: HouseholdImpactRequest,
    session: Session = Depends(get_session),
) -> HouseholdImpactResponse:
    """Calculate the impact of a policy reform on a household.

    Compares the household under baseline (current law) vs reform (policy_id).
    Returns both calculations plus computed differences.

    Use flat values for all variables - do NOT use time-period format like {"2024": value}.
    """
    with logfire.span(
        "calculate_household_impact_comparison",
        model=request.tax_benefit_model_name,
        num_people=len(request.people),
        year=request.year,
        has_policy=request.policy_id is not None,
    ):
        with logfire.span("build_baseline_request"):
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

        with logfire.span("build_reform_request"):
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
        with logfire.span("calculate_baseline"):
            baseline = calculate_household(baseline_request, session)

        with logfire.span("calculate_reform"):
            reform = calculate_household(reform_request, session)

        # Compute impact
        impact = _compute_impact(baseline, reform)

        with logfire.span("build_impact_response"):
            return HouseholdImpactResponse(
                baseline=baseline,
                reform=reform,
                impact=impact,
            )
