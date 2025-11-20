from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from policyengine_api.models import (
    ParameterValue,
    ParameterValueCreate,
    ParameterValueRead,
)
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/parameter-values", tags=["parameter-values"])


@router.post("/", response_model=ParameterValueRead)
def create_parameter_value(
    parameter_value: ParameterValueCreate, session: Session = Depends(get_session)
):
    """Create a new parameter value."""
    db_parameter_value = ParameterValue.model_validate(parameter_value)
    session.add(db_parameter_value)
    session.commit()
    session.refresh(db_parameter_value)
    return db_parameter_value


@router.get("/", response_model=List[ParameterValueRead])
def list_parameter_values(session: Session = Depends(get_session)):
    """List all parameter values."""
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


@router.delete("/{parameter_value_id}")
def delete_parameter_value(
    parameter_value_id: UUID, session: Session = Depends(get_session)
):
    """Delete a parameter value."""
    parameter_value = session.get(ParameterValue, parameter_value_id)
    if not parameter_value:
        raise HTTPException(status_code=404, detail="Parameter value not found")
    session.delete(parameter_value)
    session.commit()
    return {"message": "Parameter value deleted"}
