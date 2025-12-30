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

from policyengine_api.models import ParameterValue, ParameterValueRead
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/parameter-values", tags=["parameter-values"])


@router.get("/", response_model=List[ParameterValueRead])
def list_parameter_values(
    parameter_id: UUID | None = None,
    policy_id: UUID | None = None,
    current: bool = False,
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
    """
    query = select(ParameterValue)

    if parameter_id:
        query = query.where(ParameterValue.parameter_id == parameter_id)

    if policy_id:
        query = query.where(ParameterValue.policy_id == policy_id)

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
