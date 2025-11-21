from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi_cache.decorator import cache
from sqlmodel import Session, select

from policyengine_api.models import Parameter, ParameterCreate, ParameterRead
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/parameters", tags=["parameters"])


@router.post("/", response_model=ParameterRead)
def create_parameter(
    parameter: ParameterCreate, session: Session = Depends(get_session)
):
    """Create a new parameter."""
    db_parameter = Parameter.model_validate(parameter)
    session.add(db_parameter)
    session.commit()
    session.refresh(db_parameter)
    return db_parameter


@router.get("/", response_model=List[ParameterRead])
@cache(expire=3600)  # Cache for 1 hour
def list_parameters(
    skip: int = 0, limit: int = 100, session: Session = Depends(get_session)
):
    """List all parameters with pagination, sorted by name."""
    parameters = session.exec(
        select(Parameter).order_by(Parameter.name).offset(skip).limit(limit)
    ).all()
    return parameters


@router.get("/{parameter_id}", response_model=ParameterRead)
def get_parameter(parameter_id: UUID, session: Session = Depends(get_session)):
    """Get a specific parameter."""
    parameter = session.get(Parameter, parameter_id)
    if not parameter:
        raise HTTPException(status_code=404, detail="Parameter not found")
    return parameter


@router.delete("/{parameter_id}")
def delete_parameter(parameter_id: UUID, session: Session = Depends(get_session)):
    """Delete a parameter."""
    parameter = session.get(Parameter, parameter_id)
    if not parameter:
        raise HTTPException(status_code=404, detail="Parameter not found")
    session.delete(parameter)
    session.commit()
    return {"message": "Parameter deleted"}
