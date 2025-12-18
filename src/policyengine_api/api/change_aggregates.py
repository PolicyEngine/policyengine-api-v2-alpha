"""Change aggregate endpoints.

Change aggregates compare statistics between baseline and reform simulations
(e.g. change in tax revenue, change in poverty rate). These are typically
created automatically when processing economic impact analyses.
"""

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

router = APIRouter(prefix="/outputs/change-aggregates", tags=["change-aggregates"])


@router.post("/", response_model=List[ChangeAggregateRead])
def create_change_aggregates(
    outputs: List[ChangeAggregateCreate], session: Session = Depends(get_session)
):
    """Create change aggregate specifications comparing baseline vs reform.

    Change aggregates compute the difference in statistics between two simulations.
    """
    db_outputs = []
    for output in outputs:
        db_output = ChangeAggregate.model_validate(output)
        session.add(db_output)
        db_outputs.append(db_output)
    session.commit()
    for db_output in db_outputs:
        session.refresh(db_output)
    return db_outputs


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
