"""Tax benefit model utilities.

Shared utilities for working with tax benefit models and versions.
"""

from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, select

from policyengine_api.models import TaxBenefitModel, TaxBenefitModelVersion


def get_latest_model_version(
    tax_benefit_model_name: str, session: Session
) -> TaxBenefitModelVersion:
    """Get the latest tax benefit model version for a given model name.

    Args:
        tax_benefit_model_name: The model name (e.g., "policyengine-us" or "policyengine_us").
        session: Database session.

    Returns:
        The latest TaxBenefitModelVersion for the model.

    Raises:
        HTTPException: If model or version not found.
    """
    # Normalize model name (allow underscores or hyphens)
    model_name = tax_benefit_model_name.replace("_", "-")

    model = session.exec(
        select(TaxBenefitModel).where(TaxBenefitModel.name == model_name)
    ).first()
    if not model:
        raise HTTPException(
            status_code=404, detail=f"Tax benefit model {model_name} not found"
        )

    version = session.exec(
        select(TaxBenefitModelVersion)
        .where(TaxBenefitModelVersion.model_id == model.id)
        .order_by(TaxBenefitModelVersion.created_at.desc())
    ).first()
    if not version:
        raise HTTPException(
            status_code=404, detail=f"No version found for model {model_name}"
        )

    return version


def get_model_version_by_id(
    version_id: UUID, session: Session
) -> TaxBenefitModelVersion:
    """Get a specific tax benefit model version by ID.

    Args:
        version_id: The UUID of the model version.
        session: Database session.

    Returns:
        The TaxBenefitModelVersion with the given ID.

    Raises:
        HTTPException: If version not found.
    """
    version = session.get(TaxBenefitModelVersion, version_id)
    if not version:
        raise HTTPException(
            status_code=404, detail=f"Tax benefit model version {version_id} not found"
        )
    return version


def resolve_model_version_id(
    tax_benefit_model_name: str | None,
    tax_benefit_model_version_id: UUID | None,
    session: Session,
) -> UUID | None:
    """Resolve the model version ID from either explicit ID or model name.

    If version_id is provided, validates and returns it.
    If only model_name is provided, returns the latest version ID for that model.
    If neither is provided, returns None.

    Args:
        tax_benefit_model_name: Optional model name to get latest version for.
        tax_benefit_model_version_id: Optional explicit version ID.
        session: Database session.

    Returns:
        The resolved version ID, or None if no filtering requested.

    Raises:
        HTTPException: If specified version/model not found.
    """
    if tax_benefit_model_version_id:
        # Validate the version exists
        version = get_model_version_by_id(tax_benefit_model_version_id, session)
        return version.id
    elif tax_benefit_model_name:
        # Get the latest version for this model
        version = get_latest_model_version(tax_benefit_model_name, session)
        return version.id
    else:
        return None
