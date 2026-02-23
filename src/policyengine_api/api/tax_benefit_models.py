"""Tax-benefit model metadata endpoints.

Tax-benefit models represent country-specific microsimulation systems
(e.g. policyengine-uk, policyengine-us). Each model has versions that
define the available variables and parameters.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from policyengine_api.config.constants import COUNTRY_MODEL_NAMES, CountryId
from policyengine_api.models import (
    TaxBenefitModel,
    TaxBenefitModelRead,
    TaxBenefitModelVersion,
    TaxBenefitModelVersionRead,
)
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/tax-benefit-models", tags=["tax-benefit-models"])


@router.get("/", response_model=List[TaxBenefitModelRead])
def list_tax_benefit_models(session: Session = Depends(get_session)):
    """List available tax-benefit models.

    Models are country-specific (e.g. policyengine-uk, policyengine-us).
    Use the model name with household calculation and economic impact endpoints.
    """
    models = session.exec(select(TaxBenefitModel)).all()
    return models


class ModelByCountryResponse(BaseModel):
    """Response for the model-by-country endpoint."""

    model: TaxBenefitModelRead
    latest_version: TaxBenefitModelVersionRead


@router.get(
    "/by-country/{country_id}",
    response_model=ModelByCountryResponse,
)
def get_model_by_country(
    country_id: CountryId,
    session: Session = Depends(get_session),
):
    """Get a tax-benefit model and its latest version by country ID.

    Returns the model metadata and the most recently created version in a
    single response. Use this on page load to check the current model version
    for cache invalidation.
    """
    model_name = COUNTRY_MODEL_NAMES[country_id]

    model = session.exec(
        select(TaxBenefitModel).where(TaxBenefitModel.name == model_name)
    ).first()
    if not model:
        raise HTTPException(
            status_code=404,
            detail=f"No model found for country '{country_id}'",
        )

    latest_version = session.exec(
        select(TaxBenefitModelVersion)
        .where(TaxBenefitModelVersion.model_id == model.id)
        .order_by(TaxBenefitModelVersion.created_at.desc())
    ).first()
    if not latest_version:
        raise HTTPException(
            status_code=404,
            detail=f"No versions found for model '{model_name}'",
        )

    return ModelByCountryResponse(
        model=TaxBenefitModelRead.model_validate(model),
        latest_version=TaxBenefitModelVersionRead.model_validate(latest_version),
    )


@router.get("/{model_id}", response_model=TaxBenefitModelRead)
def get_tax_benefit_model(model_id: UUID, session: Session = Depends(get_session)):
    """Get a specific tax-benefit model."""
    model = session.get(TaxBenefitModel, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Tax-benefit model not found")
    return model
