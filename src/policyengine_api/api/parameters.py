"""Parameter metadata endpoints.

Parameters are the policy levers that can be modified in reforms (e.g. tax rates,
benefit amounts, thresholds). Use these endpoints to discover available parameters.
Parameter names are used when creating policy reforms.
"""

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
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
    session: Session = Depends(get_session),
):
    """List available parameters with pagination and search.

    Parameters are policy levers (e.g. tax rates, thresholds, benefit amounts)
    that can be modified in reforms. Use parameter names when creating policies.

    Use the `search` parameter to filter by parameter name, label, or description.
    For example: search="basic_rate" or search="income tax"
    """
    query = select(Parameter)

    if search:
        from sqlmodel import or_

        search_pattern = f"%{search}%"
        search_filter = or_(
            Parameter.name.ilike(search_pattern),
            Parameter.label.ilike(search_pattern) if Parameter.label else False,
            Parameter.description.ilike(search_pattern)
            if Parameter.description
            else False,
        )
        query = query.where(search_filter)

    parameters = session.exec(
        query.order_by(Parameter.name).offset(skip).limit(limit)
    ).all()
    return parameters


@router.get("/{parameter_id}", response_model=ParameterRead)
def get_parameter(parameter_id: UUID, session: Session = Depends(get_session)):
    """Get a specific parameter."""
    parameter = session.get(Parameter, parameter_id)
    if not parameter:
        raise HTTPException(status_code=404, detail="Parameter not found")
    return parameter
