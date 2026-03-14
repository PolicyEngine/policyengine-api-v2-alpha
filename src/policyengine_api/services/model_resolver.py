"""Shared resolver for country_id → tax-benefit model + latest version."""

from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, select

from policyengine_api.config.constants import (
    COUNTRY_MODEL_NAMES,
    MODEL_NAME_TO_COUNTRY,
    CountryId,
)
from policyengine_api.models.simulation import Simulation
from policyengine_api.models.tax_benefit_model import TaxBenefitModel
from policyengine_api.models.tax_benefit_model_version import (
    TaxBenefitModelVersion,
)


def resolve_model_name(country_id: CountryId) -> str:
    """Resolve country_id → DB model name (with hyphens)."""
    model_name = COUNTRY_MODEL_NAMES.get(country_id)
    if not model_name:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported country_id: '{country_id}'. Supported: {list(COUNTRY_MODEL_NAMES.keys())}",
        )
    return model_name


def resolve_country_model(
    country_id: CountryId, session: Session
) -> tuple[TaxBenefitModel, TaxBenefitModelVersion]:
    """Resolve country_id → (model, latest_version).

    Explicitly selects the most recent version by created_at DESC.
    """
    model_name = resolve_model_name(country_id)

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


def resolve_version_id(
    country_id: CountryId | None,
    tax_benefit_model_version_id: UUID | None,
    session: Session,
) -> UUID | None:
    """Resolve the model version ID from country_id or explicit version.

    Priority:
    1. If tax_benefit_model_version_id provided, validate and return it.
    2. If country_id provided, return the latest version's ID.
    3. If neither provided, return None (no filtering).
    """
    if tax_benefit_model_version_id:
        version = session.get(TaxBenefitModelVersion, tax_benefit_model_version_id)
        if not version:
            raise HTTPException(
                status_code=404,
                detail=f"Model version '{tax_benefit_model_version_id}' not found",
            )
        return version.id

    if country_id:
        _, version = resolve_country_model(country_id, session)
        return version.id

    return None


def resolve_country_from_simulation(sim: Simulation, session: Session) -> str:
    """Derive country_id from a simulation's model version."""
    version = session.get(TaxBenefitModelVersion, sim.tax_benefit_model_version_id)
    if not version:
        raise HTTPException(status_code=500, detail="Model version not found")
    model = session.get(TaxBenefitModel, version.model_id)
    if not model:
        raise HTTPException(status_code=500, detail="Tax-benefit model not found")
    country_id = MODEL_NAME_TO_COUNTRY.get(model.name)
    if not country_id:
        raise HTTPException(
            status_code=500,
            detail=f"Unknown model name: '{model.name}'. Expected: {list(MODEL_NAME_TO_COUNTRY.keys())}",
        )
    return country_id
