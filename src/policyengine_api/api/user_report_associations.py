"""User-report association endpoints.

Associates users with reports they've created. This enables users to
maintain a list of their reports across sessions without duplicating
the underlying report data.

Note: user_id is a client-generated UUID (via crypto.randomUUID()) stored in
the browser's localStorage. It is NOT validated against a users table, allowing
anonymous users to save reports without authentication.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from policyengine_api.config.constants import CountryId
from policyengine_api.models import (
    Report,
    UserReportAssociation,
    UserReportAssociationCreate,
    UserReportAssociationRead,
    UserReportAssociationUpdate,
)
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/user-reports", tags=["user-reports"])


@router.post("/", response_model=UserReportAssociationRead)
def create_user_report(
    body: UserReportAssociationCreate,
    session: Session = Depends(get_session),
):
    """Create a new user-report association.

    Associates a user with a report, allowing them to save it to their list.
    Duplicates are allowed - users can save the same report multiple times
    with different labels.
    """
    report = session.get(Report, body.report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    record = UserReportAssociation.model_validate(body)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@router.get("/", response_model=list[UserReportAssociationRead])
def list_user_reports(
    user_id: UUID = Query(..., description="User ID to filter by"),
    country_id: CountryId | None = Query(
        None, description="Filter by country ('us' or 'uk')"
    ),
    session: Session = Depends(get_session),
):
    """List all report associations for a user.

    Returns all reports saved by the specified user. Optionally filter by country.
    """
    query = select(UserReportAssociation).where(
        UserReportAssociation.user_id == user_id
    )

    if country_id:
        query = query.where(UserReportAssociation.country_id == country_id)

    return session.exec(query).all()


@router.get("/{user_report_id}", response_model=UserReportAssociationRead)
def get_user_report(
    user_report_id: UUID,
    session: Session = Depends(get_session),
):
    """Get a specific user-report association by ID."""
    record = session.get(UserReportAssociation, user_report_id)
    if not record:
        raise HTTPException(
            status_code=404, detail="User-report association not found"
        )
    return record


@router.patch("/{user_report_id}", response_model=UserReportAssociationRead)
def update_user_report(
    user_report_id: UUID,
    updates: UserReportAssociationUpdate,
    user_id: UUID = Query(..., description="User ID for ownership verification"),
    session: Session = Depends(get_session),
):
    """Update a user-report association (e.g., rename label or update last_run_at).

    Requires user_id to verify ownership - only the owner can update.
    """
    record = session.exec(
        select(UserReportAssociation).where(
            UserReportAssociation.id == user_report_id,
            UserReportAssociation.user_id == user_id,
        )
    ).first()
    if not record:
        raise HTTPException(
            status_code=404, detail="User-report association not found"
        )

    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(record, key, value)

    record.updated_at = datetime.now(timezone.utc)

    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@router.delete("/{user_report_id}", status_code=204)
def delete_user_report(
    user_report_id: UUID,
    user_id: UUID = Query(..., description="User ID for ownership verification"),
    session: Session = Depends(get_session),
):
    """Delete a user-report association.

    This only removes the association, not the underlying report.
    Requires user_id to verify ownership - only the owner can delete.
    """
    record = session.exec(
        select(UserReportAssociation).where(
            UserReportAssociation.id == user_report_id,
            UserReportAssociation.user_id == user_id,
        )
    ).first()
    if not record:
        raise HTTPException(
            status_code=404, detail="User-report association not found"
        )

    session.delete(record)
    session.commit()
