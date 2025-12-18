"""Behavioural dynamics endpoints.

Dynamics represent behavioural response assumptions (e.g. labour supply elasticities)
that modify how the model accounts for behavioural changes in response to policy reforms.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from policyengine_api.models import Dynamic, DynamicCreate, DynamicRead
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/dynamics", tags=["dynamics"])


@router.post("/", response_model=DynamicRead)
def create_dynamic(dynamic: DynamicCreate, session: Session = Depends(get_session)):
    """Create a new behavioural dynamics specification.

    Dynamics define behavioural response parameters. Use with household or
    economic impact endpoints via the dynamic_id parameter.
    """
    db_dynamic = Dynamic.model_validate(dynamic)
    session.add(db_dynamic)
    session.commit()
    session.refresh(db_dynamic)
    return db_dynamic


@router.get("/", response_model=List[DynamicRead])
def list_dynamics(session: Session = Depends(get_session)):
    """List all dynamics."""
    dynamics = session.exec(select(Dynamic)).all()
    return dynamics


@router.get("/{dynamic_id}", response_model=DynamicRead)
def get_dynamic(dynamic_id: UUID, session: Session = Depends(get_session)):
    """Get a specific dynamic."""
    dynamic = session.get(Dynamic, dynamic_id)
    if not dynamic:
        raise HTTPException(status_code=404, detail="Dynamic not found")
    return dynamic
