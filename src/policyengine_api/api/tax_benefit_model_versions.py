from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from policyengine_api.models import (
    TaxBenefitModelVersion,
    TaxBenefitModelVersionCreate,
    TaxBenefitModelVersionRead,
)
from policyengine_api.services.database import get_session

router = APIRouter(
    prefix="/tax-benefit-model-versions", tags=["tax-benefit-model-versions"]
)


@router.post("/", response_model=TaxBenefitModelVersionRead)
def create_tax_benefit_model_version(
    version: TaxBenefitModelVersionCreate, session: Session = Depends(get_session)
):
    """Create a new tax-benefit model version."""
    db_version = TaxBenefitModelVersion.model_validate(version)
    session.add(db_version)
    session.commit()
    session.refresh(db_version)
    return db_version


@router.get("/", response_model=List[TaxBenefitModelVersionRead])
def list_tax_benefit_model_versions(session: Session = Depends(get_session)):
    """List all tax-benefit model versions."""
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


@router.delete("/{version_id}")
def delete_tax_benefit_model_version(
    version_id: UUID, session: Session = Depends(get_session)
):
    """Delete a tax-benefit model version."""
    version = session.get(TaxBenefitModelVersion, version_id)
    if not version:
        raise HTTPException(
            status_code=404, detail="Tax-benefit model version not found"
        )
    session.delete(version)
    session.commit()
    return {"message": "Tax-benefit model version deleted"}
