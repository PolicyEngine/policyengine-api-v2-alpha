from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from policyengine_api.models import Policy, PolicyCreate, PolicyRead
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/policies", tags=["policies"])


@router.post("/", response_model=PolicyRead)
def create_policy(policy: PolicyCreate, session: Session = Depends(get_session)):
    """Create a new policy."""
    db_policy = Policy.model_validate(policy)
    session.add(db_policy)
    session.commit()
    session.refresh(db_policy)
    return db_policy


@router.get("/", response_model=List[PolicyRead])
def list_policies(session: Session = Depends(get_session)):
    """List all policies."""
    policies = session.exec(select(Policy)).all()
    return policies


@router.get("/{policy_id}", response_model=PolicyRead)
def get_policy(policy_id: UUID, session: Session = Depends(get_session)):
    """Get a specific policy."""
    policy = session.get(Policy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy
