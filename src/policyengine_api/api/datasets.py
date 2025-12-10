from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from policyengine_api.models import Dataset, DatasetRead
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("/", response_model=List[DatasetRead])
def list_datasets(session: Session = Depends(get_session)):
    """List all datasets."""
    datasets = session.exec(select(Dataset)).all()
    return datasets


@router.get("/{dataset_id}", response_model=DatasetRead)
def get_dataset(dataset_id: UUID, session: Session = Depends(get_session)):
    """Get a specific dataset."""
    dataset = session.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset
