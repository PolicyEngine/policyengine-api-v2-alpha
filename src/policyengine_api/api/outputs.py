from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from policyengine_api.models import (
    AggregateOutput,
    AggregateOutputCreate,
    AggregateOutputRead,
)
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/aggregates", tags=["aggregates"])


@router.post("/", response_model=AggregateOutputRead)
def create_aggregate_output(
    output: AggregateOutputCreate, session: Session = Depends(get_session)
):
    """Create an aggregate (worker will compute it)."""
    db_output = AggregateOutput.model_validate(output)
    session.add(db_output)
    session.commit()
    session.refresh(db_output)
    return db_output


@router.get("/", response_model=List[AggregateOutputRead])
def list_aggregate_outputs(session: Session = Depends(get_session)):
    """List all aggregates."""
    outputs = session.exec(select(AggregateOutput)).all()
    return outputs


@router.get("/{output_id}", response_model=AggregateOutputRead)
def get_aggregate_output(output_id: UUID, session: Session = Depends(get_session)):
    """Get a specific aggregate."""
    output = session.get(AggregateOutput, output_id)
    if not output:
        raise HTTPException(status_code=404, detail="Aggregate not found")
    return output
