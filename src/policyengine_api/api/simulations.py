"""Simulation status endpoints.

Simulations are economy-wide tax-benefit calculations running on population datasets.
They are created automatically when you call /analysis/economic-impact. Use these
endpoints to check simulation status (pending, running, completed, failed).
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from policyengine_api.models import Simulation, SimulationRead
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/simulations", tags=["simulations"])


@router.get("/", response_model=List[SimulationRead])
def list_simulations(session: Session = Depends(get_session)):
    """List all simulations.

    Simulations are created automatically via /analysis/economic-impact.
    Check status to see if computation is pending, running, completed, or failed.
    """
    simulations = session.exec(select(Simulation)).all()
    return simulations


@router.get("/{simulation_id}", response_model=SimulationRead)
def get_simulation(simulation_id: UUID, session: Session = Depends(get_session)):
    """Get a specific simulation."""
    simulation = session.get(Simulation, simulation_id)
    if not simulation:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return simulation
