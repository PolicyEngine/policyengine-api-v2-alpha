"""User-household association endpoints.

Associations link a user to a stored household definition with metadata
(label, country). A user can have multiple associations to the same
household (e.g. different labels or configurations).
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from policyengine_api.models import (
    Household,
    UserHouseholdAssociation,
    UserHouseholdAssociationCreate,
    UserHouseholdAssociationRead,
    UserHouseholdAssociationUpdate,
)
from policyengine_api.services.database import get_session

router = APIRouter(
    prefix="/user-household-associations",
    tags=["user-household-associations"],
)


@router.post("/", response_model=UserHouseholdAssociationRead, status_code=201)
def create_association(
    body: UserHouseholdAssociationCreate,
    session: Session = Depends(get_session),
):
    """Create a user-household association."""
    household = session.get(Household, body.household_id)
    if not household:
        raise HTTPException(
            status_code=404,
            detail=f"Household {body.household_id} not found",
        )

    record = UserHouseholdAssociation(
        user_id=body.user_id,
        household_id=body.household_id,
        country_id=body.country_id,
        label=body.label,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@router.get("/user/{user_id}", response_model=list[UserHouseholdAssociationRead])
def list_by_user(
    user_id: UUID,
    country_id: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    """List all associations for a user, optionally filtered by country."""
    query = select(UserHouseholdAssociation).where(
        UserHouseholdAssociation.user_id == user_id
    )
    if country_id is not None:
        query = query.where(UserHouseholdAssociation.country_id == country_id)
    query = query.offset(offset).limit(limit)
    return session.exec(query).all()


@router.get(
    "/{user_id}/{household_id}",
    response_model=list[UserHouseholdAssociationRead],
)
def list_by_user_and_household(
    user_id: UUID,
    household_id: UUID,
    session: Session = Depends(get_session),
):
    """List all associations for a specific user+household pair."""
    query = select(UserHouseholdAssociation).where(
        UserHouseholdAssociation.user_id == user_id,
        UserHouseholdAssociation.household_id == household_id,
    )
    return session.exec(query).all()


@router.put("/{association_id}", response_model=UserHouseholdAssociationRead)
def update_association(
    association_id: UUID,
    body: UserHouseholdAssociationUpdate,
    user_id: UUID = Query(..., description="User ID for ownership verification"),
    session: Session = Depends(get_session),
):
    """Update a user-household association (label).

    Requires user_id to verify ownership - only the owner can update.
    """
    record = session.exec(
        select(UserHouseholdAssociation).where(
            UserHouseholdAssociation.id == association_id,
            UserHouseholdAssociation.user_id == user_id,
        )
    ).first()
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"Association {association_id} not found",
        )
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(record, key, value)
    record.updated_at = datetime.now(timezone.utc)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@router.delete("/{association_id}", status_code=204)
def delete_association(
    association_id: UUID,
    user_id: UUID = Query(..., description="User ID for ownership verification"),
    session: Session = Depends(get_session),
):
    """Delete a user-household association.

    Requires user_id to verify ownership - only the owner can delete.
    """
    record = session.exec(
        select(UserHouseholdAssociation).where(
            UserHouseholdAssociation.id == association_id,
            UserHouseholdAssociation.user_id == user_id,
        )
    ).first()
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"Association {association_id} not found",
        )
    session.delete(record)
    session.commit()
