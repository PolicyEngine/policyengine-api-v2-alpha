"""Parameter value endpoints.

Parameter values represent the actual values of policy parameters at specific
time periods. These store both baseline (current law) values and reform values
when a policy modifies a parameter.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from policyengine_api.models import ParameterValue, ParameterValueRead
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/parameter-values", tags=["parameter-values"])


@router.get("/", response_model=List[ParameterValueRead])
def list_parameter_values(
    parameter_id: UUID | None = None,
    policy_id: UUID | None = None,
    skip: int = 0,
    limit: int = 100,
    session: Session = Depends(get_session),
):
    """List parameter values with optional filtering.

    Parameter values store the numeric/string values for policy parameters
    at specific time periods (start_date to end_date).

    Use `parameter_id` to filter by a specific parameter.
    Use `policy_id` to filter by a specific policy reform.
    """
    query = select(ParameterValue)

    if parameter_id:
        query = query.where(ParameterValue.parameter_id == parameter_id)

    if policy_id:
        query = query.where(ParameterValue.policy_id == policy_id)

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
