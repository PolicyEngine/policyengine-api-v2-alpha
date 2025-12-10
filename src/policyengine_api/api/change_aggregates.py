from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from policyengine_api.models import (
    ChangeAggregate,
    ChangeAggregateCreate,
    ChangeAggregateRead,
)
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/change-aggregates", tags=["change-aggregates"])


@router.post("/", response_model=ChangeAggregateRead)
def create_change_aggregate(
    output: ChangeAggregateCreate, session: Session = Depends(get_session)
):
    """Create a new change aggregate."""
    db_output = ChangeAggregate.model_validate(output)
    session.add(db_output)
    session.commit()
    session.refresh(db_output)
    return db_output


@router.get("/", response_model=List[ChangeAggregateRead])
def list_change_aggregates(session: Session = Depends(get_session)):
    """List all change aggregates."""
    outputs = session.exec(select(ChangeAggregate)).all()
    return outputs


@router.get("/{output_id}", response_model=ChangeAggregateRead)
def get_change_aggregate(output_id: UUID, session: Session = Depends(get_session)):
    """Get a specific change aggregate."""
    output = session.get(ChangeAggregate, output_id)
    if not output:
        raise HTTPException(status_code=404, detail="Change aggregate not found")
    return output
