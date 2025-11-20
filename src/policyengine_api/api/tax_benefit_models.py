from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from policyengine_api.models import (
    TaxBenefitModel,
    TaxBenefitModelCreate,
    TaxBenefitModelRead,
)
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/tax-benefit-models", tags=["tax-benefit-models"])


@router.post("/", response_model=TaxBenefitModelRead)
def create_tax_benefit_model(
    model: TaxBenefitModelCreate, session: Session = Depends(get_session)
):
    """Create a new tax-benefit model."""
    db_model = TaxBenefitModel.model_validate(model)
    session.add(db_model)
    session.commit()
    session.refresh(db_model)
    return db_model


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


@router.delete("/{model_id}")
def delete_tax_benefit_model(model_id: UUID, session: Session = Depends(get_session)):
    """Delete a tax-benefit model."""
    model = session.get(TaxBenefitModel, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Tax-benefit model not found")
    session.delete(model)
    session.commit()
    return {"message": "Tax-benefit model deleted"}
