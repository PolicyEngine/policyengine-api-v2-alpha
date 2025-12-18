"""Tax-benefit model version endpoints.

Each tax-benefit model has versions representing specific releases.
Versions define which variables and parameters are available.
The latest version is used automatically in calculations.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from policyengine_api.models import TaxBenefitModelVersion, TaxBenefitModelVersionRead
from policyengine_api.services.database import get_session

router = APIRouter(
    prefix="/tax-benefit-model-versions", tags=["tax-benefit-model-versions"]
)


@router.get("/", response_model=List[TaxBenefitModelVersionRead])
def list_tax_benefit_model_versions(session: Session = Depends(get_session)):
    """List all model versions.

    Versions represent releases of tax-benefit models with specific
    variable and parameter definitions.
    """
    versions = session.exec(select(TaxBenefitModelVersion)).all()
    return versions


@router.get("/{version_id}", response_model=TaxBenefitModelVersionRead)
def get_tax_benefit_model_version(
    version_id: UUID, session: Session = Depends(get_session)
):
    """Get a specific tax-benefit model version."""
    version = session.get(TaxBenefitModelVersion, version_id)
    if not version:
        raise HTTPException(
            status_code=404, detail="Tax-benefit model version not found"
        )
    return version
