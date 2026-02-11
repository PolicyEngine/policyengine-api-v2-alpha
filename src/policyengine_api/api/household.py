"""Household calculation endpoints.

These endpoints are async - they create jobs that are processed by Modal functions.
Poll the status endpoint until the job is complete.
"""

import math
from typing import Any, Literal
from uuid import UUID

import logfire
from fastapi import APIRouter, Depends, HTTPException
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from pydantic import BaseModel, Field
from sqlmodel import Session

from policyengine_api.models import (
    Dynamic,
    HouseholdJob,
    HouseholdJobStatus,
    Policy,
)
from policyengine_api.services.database import get_session


def _sanitize_for_json(obj: Any) -> Any:
    """Replace NaN/Inf values with None for JSON serialization."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    return obj


def get_traceparent() -> str | None:
    """Get the current W3C traceparent header for distributed tracing."""
    carrier: dict[str, str] = {}
    TraceContextTextMapPropagator().inject(carrier)
    return carrier.get("traceparent")


router = APIRouter(prefix="/household", tags=["household"])


class HouseholdCalculateRequest(BaseModel):
    """Request body for household calculation.

    IMPORTANT: Use flat values for variables, NOT time-period dictionaries.
    The year is specified separately via the `year` parameter.

    CORRECT: {"employment_income": 70000, "age": 40}
    WRONG: {"employment_income": {"2024": 70000}, "age": {"2024": 40}}

    Supports multiple households via entity relational dataframes. Include
    {entity}_id fields in each entity and person_{entity}_id fields in people
    to link them together.

    Example US request (single household, simple):
    {
        "tax_benefit_model_name": "policyengine_us",
        "people": [{"employment_income": 70000, "age": 40}],
        "tax_unit": [{"state_code": "CA"}],
        "household": [{"state_fips": 6}],
        "year": 2024
    }

    Example US request (multiple households):
    {
        "tax_benefit_model_name": "policyengine_us",
        "people": [
            {"person_id": 0, "person_household_id": 0, "person_tax_unit_id": 0, "age": 40, "employment_income": 70000},
            {"person_id": 1, "person_household_id": 1, "person_tax_unit_id": 1, "age": 30, "employment_income": 50000}
        ],
        "tax_unit": [
            {"tax_unit_id": 0, "state_code": "CA"},
            {"tax_unit_id": 1, "state_code": "NY"}
        ],
        "household": [
            {"household_id": 0, "state_fips": 6},
            {"household_id": 1, "state_fips": 36}
        ],
        "year": 2024
    }

    Example UK request:
    {
        "tax_benefit_model_name": "policyengine_uk",
        "people": [{"employment_income": 50000, "age": 30}],
        "household": [{}],
        "year": 2026
    }
    """

    tax_benefit_model_name: Literal["policyengine_uk", "policyengine_us"] = Field(
        description="Which country model to use"
    )
    people: list[dict[str, Any]] = Field(
        description="List of people with flat variable values. Include person_id and person_{entity}_id fields to link to entities."
    )
    benunit: list[dict[str, Any]] = Field(
        default_factory=list,
        description="UK benefit units. Include benunit_id to link with person_benunit_id in people.",
    )
    marital_unit: list[dict[str, Any]] = Field(
        default_factory=list,
        description="US marital units. Include marital_unit_id to link with person_marital_unit_id in people.",
    )
    family: list[dict[str, Any]] = Field(
        default_factory=list,
        description="US families. Include family_id to link with person_family_id in people.",
    )
    spm_unit: list[dict[str, Any]] = Field(
        default_factory=list,
        description="US SPM units. Include spm_unit_id to link with person_spm_unit_id in people.",
    )
    tax_unit: list[dict[str, Any]] = Field(
        default_factory=list,
        description="US tax units. Include tax_unit_id to link with person_tax_unit_id in people.",
    )
    household: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Households. Include household_id to link with person_household_id in people.",
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
    household: list[dict[str, Any]]


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
    Supports multiple households via entity relational dataframes.

    Example:
    {
        "tax_benefit_model_name": "policyengine_us",
        "people": [{"employment_income": 70000, "age": 40}],
        "tax_unit": [{"state_code": "CA"}],
        "household": [{"state_fips": 6}],
        "year": 2024,
        "policy_id": "uuid-of-reform-policy"
    }
    """

    tax_benefit_model_name: Literal["policyengine_uk", "policyengine_us"] = Field(
        description="Which country model to use"
    )
    people: list[dict[str, Any]] = Field(
        description="List of people with flat variable values. Include person_id and person_{entity}_id fields to link to entities."
    )
    benunit: list[dict[str, Any]] = Field(
        default_factory=list,
        description="UK benefit units. Include benunit_id to link with person_benunit_id in people.",
    )
    marital_unit: list[dict[str, Any]] = Field(
        default_factory=list,
        description="US marital units. Include marital_unit_id to link with person_marital_unit_id in people.",
    )
    family: list[dict[str, Any]] = Field(
        default_factory=list,
        description="US families. Include family_id to link with person_family_id in people.",
    )
    spm_unit: list[dict[str, Any]] = Field(
        default_factory=list,
        description="US SPM units. Include spm_unit_id to link with person_spm_unit_id in people.",
    )
    tax_unit: list[dict[str, Any]] = Field(
        default_factory=list,
        description="US tax units. Include tax_unit_id to link with person_tax_unit_id in people.",
    )
    household: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Households. Include household_id to link with person_household_id in people.",
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
    benunit: list[dict],
    household: list[dict],
    year: int,
    policy_data: dict | None,
    session: Session,
) -> None:
    """Run UK household calculation locally.

    Supports multiple households via entity relational dataframes.
    """
    from datetime import datetime, timezone

    try:
        result = _calculate_household_uk(people, benunit, household, year, policy_data)

        # Update job with result
        job = session.get(HouseholdJob, job_id)
        if job:
            job.status = HouseholdJobStatus.COMPLETED
            job.result = _sanitize_for_json(result)
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


def _calculate_household_uk(
    people: list[dict],
    benunit: list[dict],
    household: list[dict],
    year: int,
    policy_data: dict | None,
) -> dict:
    """Calculate UK household(s) and return result dict.

    Supports multiple households via entity relational dataframes. If entity IDs
    are not provided, defaults to single household with all people in it.
    """
    import tempfile
    from datetime import datetime
    from pathlib import Path

    import pandas as pd
    from policyengine.core import Simulation
    from microdf import MicroDataFrame
    from policyengine.tax_benefit_models.uk import uk_latest
    from policyengine.tax_benefit_models.uk.datasets import PolicyEngineUKDataset
    from policyengine.tax_benefit_models.uk.datasets import UKYearData

    n_people = len(people)
    n_benunits = max(1, len(benunit))
    n_households = max(1, len(household))

    # Build person data with defaults
    person_data = {
        "person_id": list(range(n_people)),
        "person_benunit_id": [0] * n_people,
        "person_household_id": [0] * n_people,
        "person_weight": [1.0] * n_people,
    }
    # Add user-provided person fields
    for i, person in enumerate(people):
        for key, value in person.items():
            if key not in person_data:
                person_data[key] = [0.0] * n_people
            person_data[key][i] = value

    # Build benunit data with defaults
    benunit_data = {
        "benunit_id": list(range(n_benunits)),
        "benunit_weight": [1.0] * n_benunits,
    }
    for i, bu in enumerate(benunit if benunit else [{}]):
        for key, value in bu.items():
            if key not in benunit_data:
                benunit_data[key] = [0.0] * n_benunits
            benunit_data[key][i] = value

    # Build household data with defaults
    household_data = {
        "household_id": list(range(n_households)),
        "household_weight": [1.0] * n_households,
        "region": ["LONDON"] * n_households,
        "tenure_type": ["RENT_PRIVATELY"] * n_households,
        "council_tax": [0.0] * n_households,
        "rent": [0.0] * n_households,
    }
    for i, hh in enumerate(household if household else [{}]):
        for key, value in hh.items():
            if key not in household_data:
                household_data[key] = [0.0] * n_households
            household_data[key][i] = value

    # Create MicroDataFrames
    person_df = MicroDataFrame(pd.DataFrame(person_data), weights="person_weight")
    benunit_df = MicroDataFrame(pd.DataFrame(benunit_data), weights="benunit_weight")
    household_df = MicroDataFrame(
        pd.DataFrame(household_data), weights="household_weight"
    )

    # Create temporary dataset
    tmpdir = tempfile.mkdtemp()
    filepath = str(Path(tmpdir) / "household_calc.h5")

    dataset = PolicyEngineUKDataset(
        name="Household calculation",
        description="Household(s) for calculation",
        filepath=filepath,
        year=year,
        data=UKYearData(
            person=person_df,
            benunit=benunit_df,
            household=household_df,
        ),
    )

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

    # Run simulation
    simulation = Simulation(
        dataset=dataset,
        tax_benefit_model_version=uk_latest,
        policy=policy,
    )
    simulation.run()

    # Extract outputs
    output_data = simulation.output_dataset.data

    def safe_convert(value):
        try:
            return float(value)
        except (ValueError, TypeError):
            return str(value)

    person_outputs = []
    for i in range(n_people):
        person_dict = {}
        for var in uk_latest.entity_variables["person"]:
            person_dict[var] = safe_convert(output_data.person[var].iloc[i])
        person_outputs.append(person_dict)

    benunit_outputs = []
    for i in range(len(output_data.benunit)):
        benunit_dict = {}
        for var in uk_latest.entity_variables["benunit"]:
            benunit_dict[var] = safe_convert(output_data.benunit[var].iloc[i])
        benunit_outputs.append(benunit_dict)

    household_outputs = []
    for i in range(len(output_data.household)):
        household_dict = {}
        for var in uk_latest.entity_variables["household"]:
            household_dict[var] = safe_convert(output_data.household[var].iloc[i])
        household_outputs.append(household_dict)

    return {
        "person": person_outputs,
        "benunit": benunit_outputs,
        "household": household_outputs,
    }


def _run_local_household_us(
    job_id: str,
    people: list[dict],
    marital_unit: list[dict],
    family: list[dict],
    spm_unit: list[dict],
    tax_unit: list[dict],
    household: list[dict],
    year: int,
    policy_data: dict | None,
    session: Session,
) -> None:
    """Run US household calculation locally.

    Supports multiple households via entity relational dataframes.
    """
    from datetime import datetime, timezone

    try:
        result = _calculate_household_us(
            people, marital_unit, family, spm_unit, tax_unit, household, year, policy_data
        )

        # Update job with result
        job = session.get(HouseholdJob, job_id)
        if job:
            job.status = HouseholdJobStatus.COMPLETED
            job.result = _sanitize_for_json(result)
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


def _calculate_household_us(
    people: list[dict],
    marital_unit: list[dict],
    family: list[dict],
    spm_unit: list[dict],
    tax_unit: list[dict],
    household: list[dict],
    year: int,
    policy_data: dict | None,
) -> dict:
    """Calculate US household(s) and return result dict.

    Supports multiple households via entity relational dataframes. If entity IDs
    are not provided, defaults to single household with all people in it.
    """
    import tempfile
    from datetime import datetime
    from pathlib import Path

    import pandas as pd
    from policyengine.core import Simulation
    from microdf import MicroDataFrame
    from policyengine.tax_benefit_models.us import us_latest
    from policyengine.tax_benefit_models.us.datasets import PolicyEngineUSDataset
    from policyengine.tax_benefit_models.us.datasets import USYearData

    n_people = len(people)
    n_households = max(1, len(household))
    n_marital_units = max(1, len(marital_unit))
    n_families = max(1, len(family))
    n_spm_units = max(1, len(spm_unit))
    n_tax_units = max(1, len(tax_unit))

    # Build person data with defaults
    person_data = {
        "person_id": list(range(n_people)),
        "person_household_id": [0] * n_people,
        "person_marital_unit_id": [0] * n_people,
        "person_family_id": [0] * n_people,
        "person_spm_unit_id": [0] * n_people,
        "person_tax_unit_id": [0] * n_people,
        "person_weight": [1.0] * n_people,
    }
    for i, person in enumerate(people):
        for key, value in person.items():
            if key not in person_data:
                person_data[key] = [0.0] * n_people
            person_data[key][i] = value

    # Build household data
    household_data = {
        "household_id": list(range(n_households)),
        "household_weight": [1.0] * n_households,
    }
    for i, hh in enumerate(household if household else [{}]):
        for key, value in hh.items():
            if key not in household_data:
                household_data[key] = [0.0] * n_households
            household_data[key][i] = value

    # Build marital_unit data
    marital_unit_data = {
        "marital_unit_id": list(range(n_marital_units)),
        "marital_unit_weight": [1.0] * n_marital_units,
    }
    for i, mu in enumerate(marital_unit if marital_unit else [{}]):
        for key, value in mu.items():
            if key not in marital_unit_data:
                marital_unit_data[key] = [0.0] * n_marital_units
            marital_unit_data[key][i] = value

    # Build family data
    family_data = {
        "family_id": list(range(n_families)),
        "family_weight": [1.0] * n_families,
    }
    for i, fam in enumerate(family if family else [{}]):
        for key, value in fam.items():
            if key not in family_data:
                family_data[key] = [0.0] * n_families
            family_data[key][i] = value

    # Build spm_unit data
    spm_unit_data = {
        "spm_unit_id": list(range(n_spm_units)),
        "spm_unit_weight": [1.0] * n_spm_units,
    }
    for i, spm in enumerate(spm_unit if spm_unit else [{}]):
        for key, value in spm.items():
            if key not in spm_unit_data:
                spm_unit_data[key] = [0.0] * n_spm_units
            spm_unit_data[key][i] = value

    # Build tax_unit data
    tax_unit_data = {
        "tax_unit_id": list(range(n_tax_units)),
        "tax_unit_weight": [1.0] * n_tax_units,
    }
    for i, tu in enumerate(tax_unit if tax_unit else [{}]):
        for key, value in tu.items():
            if key not in tax_unit_data:
                tax_unit_data[key] = [0.0] * n_tax_units
            tax_unit_data[key][i] = value

    # Create MicroDataFrames
    person_df = MicroDataFrame(pd.DataFrame(person_data), weights="person_weight")
    household_df = MicroDataFrame(
        pd.DataFrame(household_data), weights="household_weight"
    )
    marital_unit_df = MicroDataFrame(
        pd.DataFrame(marital_unit_data), weights="marital_unit_weight"
    )
    family_df = MicroDataFrame(pd.DataFrame(family_data), weights="family_weight")
    spm_unit_df = MicroDataFrame(pd.DataFrame(spm_unit_data), weights="spm_unit_weight")
    tax_unit_df = MicroDataFrame(pd.DataFrame(tax_unit_data), weights="tax_unit_weight")

    # Create temporary dataset
    tmpdir = tempfile.mkdtemp()
    filepath = str(Path(tmpdir) / "household_calc.h5")

    dataset = PolicyEngineUSDataset(
        name="Household calculation",
        description="Household(s) for calculation",
        filepath=filepath,
        year=year,
        data=USYearData(
            person=person_df,
            household=household_df,
            marital_unit=marital_unit_df,
            family=family_df,
            spm_unit=spm_unit_df,
            tax_unit=tax_unit_df,
        ),
    )

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

    # Run simulation
    simulation = Simulation(
        dataset=dataset,
        tax_benefit_model_version=us_latest,
        policy=policy,
    )
    simulation.run()

    # Extract outputs
    output_data = simulation.output_dataset.data

    def safe_convert(value):
        try:
            return float(value)
        except (ValueError, TypeError):
            return str(value)

    def extract_entity_outputs(entity_name: str, entity_data, n_rows: int) -> list[dict]:
        outputs = []
        for i in range(n_rows):
            row_dict = {}
            for var in us_latest.entity_variables[entity_name]:
                row_dict[var] = safe_convert(entity_data[var].iloc[i])
            outputs.append(row_dict)
        return outputs

    return {
        "person": extract_entity_outputs("person", output_data.person, n_people),
        "marital_unit": extract_entity_outputs(
            "marital_unit", output_data.marital_unit, len(output_data.marital_unit)
        ),
        "family": extract_entity_outputs(
            "family", output_data.family, len(output_data.family)
        ),
        "spm_unit": extract_entity_outputs(
            "spm_unit", output_data.spm_unit, len(output_data.spm_unit)
        ),
        "tax_unit": extract_entity_outputs(
            "tax_unit", output_data.tax_unit, len(output_data.tax_unit)
        ),
        "household": extract_entity_outputs(
            "household", output_data.household, len(output_data.household)
        ),
    }


def _trigger_modal_household(
    job_id: str,
    request: HouseholdCalculateRequest,
    policy_data: dict | None,
    dynamic_data: dict | None,
    session: Session | None = None,
) -> None:
    """Trigger household simulation - Modal or local based on settings."""
    from policyengine_api.config import settings

    if not settings.agent_use_modal and session is not None:
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

        traceparent = get_traceparent()

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
                traceparent=traceparent,
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
                traceparent=traceparent,
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
            household=job.result.get("household", []),
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

    def compute_entity_diff(
        baseline_list: list[dict], reform_list: list[dict]
    ) -> list[dict]:
        """Compute differences for a list of entity dicts."""
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

    # Compute household-level differences
    impact["household"] = compute_entity_diff(baseline.household, reform.household)

    # Compute person-level differences
    impact["person"] = compute_entity_diff(baseline.person, reform.person)

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
            household=baseline_job.result.get("household", []),
        )
        reform_result = HouseholdCalculateResponse(
            person=reform_job.result.get("person", []),
            benunit=reform_job.result.get("benunit"),
            marital_unit=reform_job.result.get("marital_unit"),
            family=reform_job.result.get("family"),
            spm_unit=reform_job.result.get("spm_unit"),
            tax_unit=reform_job.result.get("tax_unit"),
            household=reform_job.result.get("household", []),
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
