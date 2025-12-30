"""Parameter metadata endpoints.

Parameters are the policy levers that can be modified in reforms (e.g. tax rates,
benefit amounts, thresholds). Use these endpoints to discover available parameters.
Parameter names are used when creating policy reforms.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from policyengine_api.models import (
    Parameter,
    ParameterRead,
    TaxBenefitModel,
    TaxBenefitModelVersion,
)
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/parameters", tags=["parameters"])


@router.get("/", response_model=List[ParameterRead])
def list_parameters(
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
    tax_benefit_model_name: str | None = None,
    session: Session = Depends(get_session),
):
    """List available parameters with pagination and search.

    Parameters are policy levers (e.g. tax rates, thresholds, benefit amounts)
    that can be modified in reforms. Use parameter names when creating policies.

    Args:
        search: Filter by parameter name, label, or description.
        tax_benefit_model_name: Filter by country model.
            Use "policyengine-uk" for UK parameters.
            Use "policyengine-us" for US parameters.
    """
    query = select(Parameter)

    # Filter by tax benefit model name (country)
    if tax_benefit_model_name:
        query = (
            query.join(TaxBenefitModelVersion)
            .join(TaxBenefitModel)
            .where(TaxBenefitModel.name == tax_benefit_model_name)
        )

    if search:
        # Case-insensitive search using ILIKE
        search_pattern = f"%{search}%"
        search_filter = (
            Parameter.name.ilike(search_pattern)
            | Parameter.label.ilike(search_pattern)
            | Parameter.description.ilike(search_pattern)
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
