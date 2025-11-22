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
from policyengine_api.tasks.runner import compute_aggregate_task

router = APIRouter(prefix="/outputs", tags=["outputs"])


@router.post("/aggregate", response_model=AggregateOutputRead)
def create_aggregate_output(
    output: AggregateOutputCreate, session: Session = Depends(get_session)
):
    """Create and compute an aggregate."""
    db_output = AggregateOutput.model_validate(output)
    session.add(db_output)
    session.commit()
    session.refresh(db_output)

    # Queue computation task
    compute_aggregate_task.delay(str(db_output.id))

    return db_output


@router.get("/aggregate", response_model=List[AggregateOutputRead])
def list_aggregate_outputs(session: Session = Depends(get_session)):
    """List all aggregates."""
    outputs = session.exec(select(AggregateOutput)).all()
    return outputs


@router.get("/aggregate/{output_id}", response_model=AggregateOutputRead)
def get_aggregate_output(output_id: UUID, session: Session = Depends(get_session)):
    """Get a specific aggregate."""
    output = session.get(AggregateOutput, output_id)
    if not output:
        raise HTTPException(status_code=404, detail="Aggregate not found")
    return output
