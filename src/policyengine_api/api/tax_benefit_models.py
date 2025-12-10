from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from policyengine_api.models import TaxBenefitModel, TaxBenefitModelRead
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/tax-benefit-models", tags=["tax-benefit-models"])


@router.get("/", response_model=List[TaxBenefitModelRead])
def list_tax_benefit_models(session: Session = Depends(get_session)):
    """List all tax-benefit models."""
    models = session.exec(select(TaxBenefitModel)).all()
    return models


@router.get("/{model_id}", response_model=TaxBenefitModelRead)
def get_tax_benefit_model(model_id: UUID, session: Session = Depends(get_session)):
    """Get a specific tax-benefit model."""
    model = session.get(TaxBenefitModel, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Tax-benefit model not found")
    return model
