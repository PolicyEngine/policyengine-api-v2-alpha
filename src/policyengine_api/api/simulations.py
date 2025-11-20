from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from policyengine_api.models import Simulation, SimulationCreate, SimulationRead
from policyengine_api.services.database import get_session
from policyengine_api.tasks.runner import run_simulation_task

router = APIRouter(prefix="/simulations", tags=["simulations"])


@router.post("/", response_model=SimulationRead)
def create_simulation(
    simulation: SimulationCreate, session: Session = Depends(get_session)
):
    """Create and queue a new simulation."""
    db_simulation = Simulation.model_validate(simulation)
    session.add(db_simulation)
    session.commit()
    session.refresh(db_simulation)

    # Queue simulation task
    run_simulation_task.delay(str(db_simulation.id))

    return db_simulation


@router.get("/", response_model=List[SimulationRead])
def list_simulations(session: Session = Depends(get_session)):
    """List all simulations."""
    simulations = session.exec(select(Simulation)).all()
    return simulations


@router.get("/{simulation_id}", response_model=SimulationRead)
def get_simulation(simulation_id: UUID, session: Session = Depends(get_session)):
    """Get a specific simulation."""
    simulation = session.get(Simulation, simulation_id)
    if not simulation:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return simulation
