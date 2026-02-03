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
    Duplicates are allowed - users can save the same policy multiple times
    with different labels (matching FE localStorage behavior).
    """
    # Validate user exists
    user = session.get(User, user_policy.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate policy exists
    policy = session.get(Policy, user_policy.policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    # Create the association (duplicates allowed)
    db_user_policy = UserPolicy.model_validate(user_policy)
    session.add(db_user_policy)
    session.commit()
    session.refresh(db_user_policy)
    return db_user_policy


@router.get("/", response_model=list[UserPolicyRead])
def list_user_policies(
    user_id: UUID = Query(..., description="User ID to filter by"),
    tax_benefit_model_id: UUID | None = Query(None, description="Filter by tax benefit model"),
    session: Session = Depends(get_session),
):
    """List all policy associations for a user.

    Returns all policies saved by the specified user. Optionally filter by tax benefit model.
    """
    query = select(UserPolicy).where(UserPolicy.user_id == user_id)

    if tax_benefit_model_id:
        query = (
            query
            .join(Policy, UserPolicy.policy_id == Policy.id)
            .where(Policy.tax_benefit_model_id == tax_benefit_model_id)
        )

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
