"""Parameter value endpoints.

Parameter values represent the actual values of policy parameters at specific
time periods. These store both baseline (current law) values and reform values
when a policy modifies a parameter.
"""

from datetime import datetime, timezone
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, or_, select

from policyengine_api.models import Parameter, ParameterValue, ParameterValueRead
from policyengine_api.services.database import get_session
from policyengine_api.services.tax_benefit_models import resolve_model_version_id

router = APIRouter(prefix="/parameter-values", tags=["parameter-values"])


@router.get("/", response_model=List[ParameterValueRead])
def list_parameter_values(
    parameter_id: UUID | None = None,
    policy_id: UUID | None = None,
    current: bool = False,
    tax_benefit_model_name: str | None = None,
    tax_benefit_model_version_id: UUID | None = None,
    skip: int = 0,
    limit: int = 100,
    session: Session = Depends(get_session),
):
    """List parameter values with optional filtering.

    Parameter values store the numeric/string values for policy parameters
    at specific time periods (start_date to end_date).

    Args:
        parameter_id: Filter by a specific parameter.
        policy_id: Filter by a specific policy reform.
        current: If true, only return values that are currently in effect
            (start_date <= now and (end_date is null or end_date > now)).
        tax_benefit_model_name: Filter by country model name.
            Use "policyengine-uk" for UK parameter values.
            Use "policyengine-us" for US parameter values.
            When specified without version_id, returns values from the latest version.
        tax_benefit_model_version_id: Filter by specific model version UUID.
            Takes precedence over tax_benefit_model_name if both are provided.
    """
    query = select(ParameterValue)

    if parameter_id:
        query = query.where(ParameterValue.parameter_id == parameter_id)

    if policy_id:
        query = query.where(ParameterValue.policy_id == policy_id)

    # Resolve version ID from either explicit ID or model name (defaults to latest)
    version_id = resolve_model_version_id(
        tax_benefit_model_name, tax_benefit_model_version_id, session
    )

    if version_id:
        # Join through Parameter to filter by model version
        query = query.join(Parameter).where(
            Parameter.tax_benefit_model_version_id == version_id
        )

    if current:
        now = datetime.now(timezone.utc)
        query = query.where(
            ParameterValue.start_date <= now,
            or_(
                ParameterValue.end_date.is_(None),
                ParameterValue.end_date > now,
            ),
        )

    # Order by start_date descending so most recent values come first
    query = query.order_by(ParameterValue.start_date.desc())

    parameter_values = session.exec(query.offset(skip).limit(limit)).all()
    return parameter_values


@router.get("/{parameter_value_id}", response_model=ParameterValueRead)
def get_parameter_value(
    parameter_value_id: UUID, session: Session = Depends(get_session)
):
    """Get a specific parameter value."""
    parameter_value = session.get(ParameterValue, parameter_value_id)
    if not parameter_value:
        raise HTTPException(status_code=404, detail="Parameter value not found")
    return parameter_value
