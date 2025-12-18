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
def list_parameter_values(session: Session = Depends(get_session)):
    """List all parameter values.

    Parameter values store the numeric/string values for policy parameters
    at specific time periods (start_date to end_date).
    """
    parameter_values = session.exec(select(ParameterValue)).all()
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
