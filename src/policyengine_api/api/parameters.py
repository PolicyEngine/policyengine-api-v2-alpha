from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi_cache.decorator import cache
from sqlmodel import Session, select

from policyengine_api.models import Parameter, ParameterRead
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/parameters", tags=["parameters"])


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
