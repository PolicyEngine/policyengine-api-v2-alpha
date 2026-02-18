"""User-simulation association endpoints.

Associates users with simulations they've run. This enables users to
maintain a list of their simulations across sessions without duplicating
the underlying simulation data.

Note: user_id is a client-generated UUID (via crypto.randomUUID()) stored in
the browser's localStorage. It is NOT validated against a users table, allowing
anonymous users to save simulations without authentication.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from policyengine_api.config.constants import CountryId
from policyengine_api.models import (
    Simulation,
    UserSimulationAssociation,
    UserSimulationAssociationCreate,
    UserSimulationAssociationRead,
    UserSimulationAssociationUpdate,
)
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/user-simulations", tags=["user-simulations"])


@router.post("/", response_model=UserSimulationAssociationRead)
def create_user_simulation(
    body: UserSimulationAssociationCreate,
    session: Session = Depends(get_session),
):
    """Create a new user-simulation association.

    Associates a user with a simulation, allowing them to save it to their list.
    Duplicates are allowed - users can save the same simulation multiple times
    with different labels.
    """
    simulation = session.get(Simulation, body.simulation_id)
    if not simulation:
        raise HTTPException(status_code=404, detail="Simulation not found")

    record = UserSimulationAssociation.model_validate(body)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@router.get("/", response_model=list[UserSimulationAssociationRead])
def list_user_simulations(
    user_id: UUID = Query(..., description="User ID to filter by"),
    country_id: CountryId | None = Query(
        None, description="Filter by country ('us' or 'uk')"
    ),
    session: Session = Depends(get_session),
):
    """List all simulation associations for a user.

    Returns all simulations saved by the specified user. Optionally filter by country.
    """
    query = select(UserSimulationAssociation).where(
        UserSimulationAssociation.user_id == user_id
    )

    if country_id:
        query = query.where(UserSimulationAssociation.country_id == country_id)

    return session.exec(query).all()


@router.get("/{user_simulation_id}", response_model=UserSimulationAssociationRead)
def get_user_simulation(
    user_simulation_id: UUID,
    session: Session = Depends(get_session),
):
    """Get a specific user-simulation association by ID."""
    record = session.get(UserSimulationAssociation, user_simulation_id)
    if not record:
        raise HTTPException(
            status_code=404, detail="User-simulation association not found"
        )
    return record


@router.patch("/{user_simulation_id}", response_model=UserSimulationAssociationRead)
def update_user_simulation(
    user_simulation_id: UUID,
    updates: UserSimulationAssociationUpdate,
    user_id: UUID = Query(..., description="User ID for ownership verification"),
    session: Session = Depends(get_session),
):
    """Update a user-simulation association (e.g., rename label).

    Requires user_id to verify ownership - only the owner can update.
    """
    record = session.exec(
        select(UserSimulationAssociation).where(
            UserSimulationAssociation.id == user_simulation_id,
            UserSimulationAssociation.user_id == user_id,
        )
    ).first()
    if not record:
        raise HTTPException(
            status_code=404, detail="User-simulation association not found"
        )

    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(record, key, value)

    record.updated_at = datetime.now(timezone.utc)

    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@router.delete("/{user_simulation_id}", status_code=204)
def delete_user_simulation(
    user_simulation_id: UUID,
    user_id: UUID = Query(..., description="User ID for ownership verification"),
    session: Session = Depends(get_session),
):
    """Delete a user-simulation association.

    This only removes the association, not the underlying simulation.
    Requires user_id to verify ownership - only the owner can delete.
    """
    record = session.exec(
        select(UserSimulationAssociation).where(
            UserSimulationAssociation.id == user_simulation_id,
            UserSimulationAssociation.user_id == user_id,
        )
    ).first()
    if not record:
        raise HTTPException(
            status_code=404, detail="User-simulation association not found"
        )

    session.delete(record)
    session.commit()
