from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi_cache.decorator import cache
from sqlmodel import Session, select

from policyengine_api.models import Variable, VariableRead
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/variables", tags=["variables"])


@router.get("/", response_model=List[VariableRead])
@cache(expire=3600)  # Cache for 1 hour
def list_variables(
    skip: int = 0, limit: int = 100, session: Session = Depends(get_session)
):
    """List all variables with pagination, sorted by name."""
    variables = session.exec(
        select(Variable).order_by(Variable.name).offset(skip).limit(limit)
    ).all()
    return variables


@router.get("/{variable_id}", response_model=VariableRead)
def get_variable(variable_id: UUID, session: Session = Depends(get_session)):
    """Get a specific variable."""
    variable = session.get(Variable, variable_id)
    if not variable:
        raise HTTPException(status_code=404, detail="Variable not found")
    return variable
