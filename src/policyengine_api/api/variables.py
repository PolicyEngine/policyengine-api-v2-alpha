"""Variable metadata endpoints.

Variables are the inputs and outputs of tax-benefit calculations. Use these
endpoints to discover what variables exist (e.g. employment_income, income_tax)
and their metadata. Variable names can be used in household calculation requests.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from policyengine_api.config.constants import COUNTRY_MODEL_NAMES, CountryId
from policyengine_api.models import (
    TaxBenefitModel,
    TaxBenefitModelVersion,
    Variable,
    VariableRead,
)
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/variables", tags=["variables"])


@router.get("/", response_model=List[VariableRead])
def list_variables(
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
    tax_benefit_model_name: str | None = None,
    session: Session = Depends(get_session),
):
    """List available variables with pagination and search.

    Variables are inputs (e.g. employment_income, age) and outputs (e.g. income_tax,
    household_net_income) of tax-benefit calculations. Use variable names in
    household calculation requests.

    Args:
        search: Filter by variable name, label, or description.
        tax_benefit_model_name: Filter by country model.
            Use "policyengine-uk" for UK variables.
            Use "policyengine-us" for US variables.
    """
    query = select(Variable)

    # Filter by tax benefit model name (country)
    if tax_benefit_model_name:
        query = (
            query.join(TaxBenefitModelVersion)
            .join(TaxBenefitModel)
            .where(TaxBenefitModel.name == tax_benefit_model_name)
        )

    if search:
        # Case-insensitive search using ILIKE
        # Note: Variables don't have a label field, only name and description
        search_pattern = f"%{search}%"
        search_filter = Variable.name.ilike(
            search_pattern
        ) | Variable.description.ilike(search_pattern)
        query = query.where(search_filter)

    variables = session.exec(
        query.order_by(Variable.name).offset(skip).limit(limit)
    ).all()
    return variables


class VariableByNameRequest(BaseModel):
    """Request body for looking up variables by name."""

    names: list[str]
    country_id: CountryId


@router.post("/by-name", response_model=List[VariableRead])
def get_variables_by_name(
    request: VariableByNameRequest,
    session: Session = Depends(get_session),
):
    """Look up variables by their exact names.

    Given a list of variable names (e.g. "employment_income", "income_tax"),
    returns the full metadata for each matching variable. Names that don't
    match any variable are silently omitted from the response.

    Use this to fetch metadata for a known set of variables (e.g. variables
    used in a household builder or report output) without loading the entire
    variable catalog.
    """
    if not request.names:
        return []

    model_name = COUNTRY_MODEL_NAMES[request.country_id]
    query = (
        select(Variable)
        .join(TaxBenefitModelVersion)
        .join(TaxBenefitModel)
        .where(TaxBenefitModel.name == model_name)
        .where(Variable.name.in_(request.names))
        .order_by(Variable.name)
    )

    return session.exec(query).all()


@router.get("/{variable_id}", response_model=VariableRead)
def get_variable(variable_id: UUID, session: Session = Depends(get_session)):
    """Get a specific variable."""
    variable = session.get(Variable, variable_id)
    if not variable:
        raise HTTPException(status_code=404, detail="Variable not found")
    return variable
