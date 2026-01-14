"""User-policy association endpoints.

Associates users with policies they've saved/created. This enables users to
maintain a list of their policies across sessions without duplicating the
underlying policy data.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from policyengine_api.models import (
    Policy,
    User,
    UserPolicy,
    UserPolicyCreate,
    UserPolicyRead,
    UserPolicyUpdate,
)
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/user-policies", tags=["user-policies"])


@router.post("/", response_model=UserPolicyRead)
def create_user_policy(
    user_policy: UserPolicyCreate,
    session: Session = Depends(get_session),
):
    """Create a new user-policy association.

    Associates a user with a policy, allowing them to save it to their list.
    A user can only have one association per policy (duplicates are rejected).
    """
    # Validate user exists
    user = session.get(User, user_policy.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate policy exists
    policy = session.get(Policy, user_policy.policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    # Check for duplicate (same user_id + policy_id)
    existing = session.exec(
        select(UserPolicy).where(
            UserPolicy.user_id == user_policy.user_id,
            UserPolicy.policy_id == user_policy.policy_id,
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail="User already has an association with this policy",
        )

    # Create the association
    db_user_policy = UserPolicy.model_validate(user_policy)
    session.add(db_user_policy)
    session.commit()
    session.refresh(db_user_policy)
    return db_user_policy


@router.get("/", response_model=list[UserPolicyRead])
def list_user_policies(
    user_id: UUID = Query(..., description="User ID to filter by"),
    country_id: str | None = Query(None, description="Country filter (us/uk)"),
    session: Session = Depends(get_session),
):
    """List all policy associations for a user.

    Returns all policies saved by the specified user. Optionally filter by country.
    """
    query = select(UserPolicy).where(UserPolicy.user_id == user_id)

    if country_id:
        query = query.where(UserPolicy.country_id == country_id)

    user_policies = session.exec(query).all()
    return user_policies


@router.get("/{user_policy_id}", response_model=UserPolicyRead)
def get_user_policy(
    user_policy_id: UUID,
    session: Session = Depends(get_session),
):
    """Get a specific user-policy association by ID."""
    user_policy = session.get(UserPolicy, user_policy_id)
    if not user_policy:
        raise HTTPException(status_code=404, detail="User-policy association not found")
    return user_policy


@router.patch("/{user_policy_id}", response_model=UserPolicyRead)
def update_user_policy(
    user_policy_id: UUID,
    updates: UserPolicyUpdate,
    session: Session = Depends(get_session),
):
    """Update a user-policy association (e.g., rename label)."""
    user_policy = session.get(UserPolicy, user_policy_id)
    if not user_policy:
        raise HTTPException(status_code=404, detail="User-policy association not found")

    # Apply updates
    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user_policy, key, value)

    # Update timestamp
    user_policy.updated_at = datetime.now(timezone.utc)

    session.add(user_policy)
    session.commit()
    session.refresh(user_policy)
    return user_policy


@router.delete("/{user_policy_id}", status_code=204)
def delete_user_policy(
    user_policy_id: UUID,
    session: Session = Depends(get_session),
):
    """Delete a user-policy association.

    This only removes the association, not the underlying policy.
    """
    user_policy = session.get(UserPolicy, user_policy_id)
    if not user_policy:
        raise HTTPException(status_code=404, detail="User-policy association not found")

    session.delete(user_policy)
    session.commit()
