"""Aggregate output endpoints.

Aggregates are computed statistics from simulations (e.g. total tax revenue,
benefit spending, poverty rates). Computation is triggered on Modal.
"""

from typing import List
from uuid import UUID

import logfire
import modal
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select

from policyengine_api.models import (
    AggregateOutput,
    AggregateOutputCreate,
    AggregateOutputRead,
    Simulation,
    TaxBenefitModel,
    TaxBenefitModelVersion,
)
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/outputs/aggregates", tags=["aggregates"])


def _get_traceparent() -> str | None:
    """Get W3C traceparent from current span context."""
    try:
        from opentelemetry import trace
        from opentelemetry.trace.propagation.tracecontext import (
            TraceContextTextMapPropagator,
        )

        carrier: dict[str, str] = {}
        TraceContextTextMapPropagator().inject(
            carrier, trace.set_span_in_context(trace.get_current_span())
        )
        return carrier.get("traceparent")
    except Exception:
        return None


def _trigger_aggregate_computation(
    aggregate_id: str, simulation_id: UUID, session: Session
) -> None:
    """Trigger aggregate computation on Modal."""
    # Look up simulation to determine UK/US
    simulation = session.get(Simulation, simulation_id)
    if not simulation:
        logfire.error("Simulation not found", simulation_id=str(simulation_id))
        return

    model_version = session.get(
        TaxBenefitModelVersion, simulation.tax_benefit_model_version_id
    )
    if not model_version:
        logfire.error(
            "Model version not found",
            version_id=str(simulation.tax_benefit_model_version_id),
        )
        return

    model = session.get(TaxBenefitModel, model_version.model_id)
    if not model:
        logfire.error("Model not found", model_id=str(model_version.model_id))
        return

    traceparent = _get_traceparent()

    if "uk" in model.name.lower():
        fn = modal.Function.from_name("policyengine", "compute_aggregate_uk")
    else:
        fn = modal.Function.from_name("policyengine", "compute_aggregate_us")

    fn.spawn(aggregate_id=aggregate_id, traceparent=traceparent)
    logfire.info(
        "Triggered aggregate computation",
        aggregate_id=aggregate_id,
        model=model.name,
    )


@router.post("/", response_model=List[AggregateOutputRead])
def create_aggregate_outputs(
    outputs: List[AggregateOutputCreate],
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """Create aggregate output specifications and trigger computation.

    Aggregates are statistics like sums, means, or counts of simulation variables.
    Computation happens asynchronously on Modal. Poll GET /outputs/aggregates/{id}
    until status="completed" to get results.
    """
    # Validate all simulations exist first
    for output in outputs:
        simulation = session.get(Simulation, output.simulation_id)
        if not simulation:
            raise HTTPException(
                status_code=404,
                detail=f"Simulation {output.simulation_id} not found",
            )

    db_outputs = []
    for output in outputs:
        db_output = AggregateOutput.model_validate(output)
        session.add(db_output)
        db_outputs.append(db_output)
    session.commit()
    for db_output in db_outputs:
        session.refresh(db_output)

    # Trigger computation for each aggregate
    for db_output in db_outputs:
        _trigger_aggregate_computation(
            str(db_output.id), db_output.simulation_id, session
        )

    return db_outputs


@router.get("/", response_model=List[AggregateOutputRead])
def list_aggregate_outputs(session: Session = Depends(get_session)):
    """List all aggregates."""
    outputs = session.exec(select(AggregateOutput)).all()
    return outputs


@router.get("/{output_id}", response_model=AggregateOutputRead)
def get_aggregate_output(output_id: UUID, session: Session = Depends(get_session)):
    """Get a specific aggregate."""
    output = session.get(AggregateOutput, output_id)
    if not output:
        raise HTTPException(status_code=404, detail="Aggregate not found")
    return output
