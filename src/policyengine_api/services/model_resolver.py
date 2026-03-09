"""Shared resolver for country_id → tax-benefit model + latest version."""

from fastapi import HTTPException
from sqlmodel import Session, select

from policyengine_api.config.constants import COUNTRY_MODEL_NAMES, CountryId
from policyengine_api.models.tax_benefit_model import TaxBenefitModel
from policyengine_api.models.tax_benefit_model_version import (
    TaxBenefitModelVersion,
)


def resolve_model_name(country_id: CountryId) -> str:
    """Resolve country_id → DB model name (with hyphens)."""
    return COUNTRY_MODEL_NAMES[country_id]


def resolve_country_model(
    country_id: CountryId, session: Session
) -> tuple[TaxBenefitModel, TaxBenefitModelVersion]:
    """Resolve country_id → (model, latest_version).

    Explicitly selects the most recent version by created_at DESC.
    """
    model_name = COUNTRY_MODEL_NAMES[country_id]

    model = session.exec(
        select(TaxBenefitModel).where(TaxBenefitModel.name == model_name)
    ).first()
    if not model:
        raise HTTPException(
            status_code=404, detail=f"Model not found for country: {country_id}"
        )

    version = session.exec(
        select(TaxBenefitModelVersion)
        .where(TaxBenefitModelVersion.model_id == model.id)
        .order_by(TaxBenefitModelVersion.created_at.desc())
    ).first()
    if not version:
        raise HTTPException(
            status_code=404,
            detail=f"No version found for model: {model_name}",
        )

    return model, version
