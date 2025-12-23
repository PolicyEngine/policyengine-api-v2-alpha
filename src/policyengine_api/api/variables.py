"""Variable metadata endpoints.

Variables are the inputs and outputs of tax-benefit calculations. Use these
endpoints to discover what variables exist (e.g. employment_income, income_tax)
and their metadata. Variable names can be used in household calculation requests.

Use the `search` parameter to filter variables by name, entity, or description.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_cache.decorator import cache
from sqlmodel import Session, or_, select

from policyengine_api.models import Variable, VariableRead
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/variables", tags=["variables"])


@router.get("/", response_model=List[VariableRead])
@cache(expire=3600)  # Cache for 1 hour
def list_variables(
    skip: int = 0,
    limit: int = 100,
    search: str | None = Query(
        default=None, description="Search by variable name, entity, or description"
    ),
    entity: str | None = Query(
        default=None,
        description="Filter by entity type (e.g. person, household, benunit, tax_unit)",
    ),
    session: Session = Depends(get_session),
):
    """List available variables with pagination and search.

    Variables are inputs (e.g. employment_income, age) and outputs (e.g. income_tax,
    household_net_income) of tax-benefit calculations. Use variable names in
    household calculation requests.

    Use the `search` parameter to filter by name, entity, or description.
    For example: search="income_tax" or search="universal credit"
    """
    query = select(Variable)

    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                Variable.name.ilike(search_pattern),
                Variable.entity.ilike(search_pattern),
                Variable.description.ilike(search_pattern)
                if Variable.description
                else False,
            )
        )

    if entity:
        query = query.where(Variable.entity == entity)

    query = query.order_by(Variable.name).offset(skip).limit(limit)
    variables = session.exec(query).all()
    return variables


@router.get("/{variable_id}", response_model=VariableRead)
def get_variable(variable_id: UUID, session: Session = Depends(get_session)):
    """Get a specific variable."""
    variable = session.get(Variable, variable_id)
    if not variable:
        raise HTTPException(status_code=404, detail="Variable not found")
    return variable
