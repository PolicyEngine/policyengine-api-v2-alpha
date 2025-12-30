"""Dataset endpoints for accessing microdata used in simulations.

Datasets contain population microdata (e.g. survey data) used to run
economy-wide tax-benefit simulations. Use these endpoints to discover
available datasets and get their IDs for use with the economic-impact endpoint.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from policyengine_api.models import Dataset, DatasetRead, TaxBenefitModel
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("/", response_model=List[DatasetRead])
def list_datasets(
    tax_benefit_model_name: str | None = None,
    session: Session = Depends(get_session),
):
    """List available datasets.

    Returns datasets that can be used with the /analysis/economic-impact endpoint.
    Each dataset represents population microdata for a specific country and year.

    Args:
        tax_benefit_model_name: Filter by country model.
            Use "policyengine-uk" for UK datasets.
            Use "policyengine-us" for US datasets.
    """
    query = select(Dataset)

    if tax_benefit_model_name:
        query = query.join(TaxBenefitModel).where(
            TaxBenefitModel.name == tax_benefit_model_name
        )

    datasets = session.exec(query).all()
    return datasets


@router.get("/{dataset_id}", response_model=DatasetRead)
def get_dataset(dataset_id: UUID, session: Session = Depends(get_session)):
    """Get a specific dataset."""
    dataset = session.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset
