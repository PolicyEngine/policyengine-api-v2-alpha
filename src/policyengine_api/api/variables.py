"""Variable metadata endpoints.

Variables are the inputs and outputs of tax-benefit calculations. Use these
endpoints to discover what variables exist (e.g. employment_income, income_tax)
and their metadata. Variable names can be used in household calculation requests.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from policyengine_api.models import (
    Variable,
    VariableRead,
)
from policyengine_api.services.database import get_session
from policyengine_api.services.tax_benefit_models import resolve_model_version_id

router = APIRouter(prefix="/variables", tags=["variables"])


@router.get("/", response_model=List[VariableRead])
def list_variables(
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
    tax_benefit_model_name: str | None = None,
    tax_benefit_model_version_id: UUID | None = None,
    session: Session = Depends(get_session),
):
    """List available variables with pagination and search.

    Variables are inputs (e.g. employment_income, age) and outputs (e.g. income_tax,
    household_net_income) of tax-benefit calculations. Use variable names in
    household calculation requests.

    Args:
        search: Filter by variable name, label, or description.
        tax_benefit_model_name: Filter by country model name.
            Use "policyengine-uk" for UK variables.
            Use "policyengine-us" for US variables.
            When specified without version_id, returns variables from the latest version.
        tax_benefit_model_version_id: Filter by specific model version UUID.
            Takes precedence over tax_benefit_model_name if both are provided.
    """
    query = select(Variable)

    # Resolve version ID from either explicit ID or model name (defaults to latest)
    version_id = resolve_model_version_id(
        tax_benefit_model_name, tax_benefit_model_version_id, session
    )

    if version_id:
        query = query.where(Variable.tax_benefit_model_version_id == version_id)

    if search:
        # Case-insensitive search using ILIKE
        # Note: Variables don't have a label field, only name and description
        search_pattern = f"%{search}%"
        search_filter = Variable.name.ilike(search_pattern) | Variable.description.ilike(
            search_pattern
        )
        query = query.where(search_filter)

    variables = session.exec(
        query.order_by(Variable.name).offset(skip).limit(limit)
    ).all()
    return variables


@router.get("/{variable_id}", response_model=VariableRead)
def get_variable(variable_id: UUID, session: Session = Depends(get_session)):
    """Get a specific variable."""
    variable = session.get(Variable, variable_id)
    if not variable:
        raise HTTPException(status_code=404, detail="Variable not found")
    return variable
