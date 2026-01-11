"""Change aggregate endpoints.

Change aggregates compare statistics between baseline and reform simulations
(e.g. change in tax revenue, change in poverty rate). Computation is triggered
on Modal.
"""

from typing import List
from uuid import UUID

import logfire
import modal
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select

from policyengine_api.models import (
    ChangeAggregate,
    ChangeAggregateCreate,
    ChangeAggregateRead,
    Simulation,
    TaxBenefitModel,
    TaxBenefitModelVersion,
)
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/outputs/change-aggregates", tags=["change-aggregates"])


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


def _trigger_change_aggregate_computation(
    change_aggregate_id: str, baseline_simulation_id: UUID, session: Session
) -> None:
    """Trigger change aggregate computation on Modal."""
    # Look up simulation to determine UK/US
    simulation = session.get(Simulation, baseline_simulation_id)
    if not simulation:
        logfire.error("Simulation not found", simulation_id=str(baseline_simulation_id))
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

    model = session.get(TaxBenefitModel, model_version.tax_benefit_model_id)
    if not model:
        logfire.error(
            "Model not found", model_id=str(model_version.tax_benefit_model_id)
        )
        return

    traceparent = _get_traceparent()

    if model.name == "uk" or model.name == "policyengine_uk":
        fn = modal.Function.from_name("policyengine", "compute_change_aggregate_uk")
    else:
        fn = modal.Function.from_name("policyengine", "compute_change_aggregate_us")

    fn.spawn(change_aggregate_id=change_aggregate_id, traceparent=traceparent)
    logfire.info(
        "Triggered change aggregate computation",
        change_aggregate_id=change_aggregate_id,
        model=model.name,
    )


@router.post("/", response_model=List[ChangeAggregateRead])
def create_change_aggregates(
    outputs: List[ChangeAggregateCreate],
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """Create change aggregate specifications and trigger computation.

    Change aggregates compute the difference in statistics between two simulations.
    Computation happens asynchronously on Modal. Poll GET /outputs/change-aggregates/{id}
    until status="completed" to get results.
    """
    db_outputs = []
    for output in outputs:
        db_output = ChangeAggregate.model_validate(output)
        session.add(db_output)
        db_outputs.append(db_output)
    session.commit()
    for db_output in db_outputs:
        session.refresh(db_output)

    # Trigger computation for each change aggregate
    for db_output in db_outputs:
        _trigger_change_aggregate_computation(
            str(db_output.id), db_output.baseline_simulation_id, session
        )

    return db_outputs


@router.get("/", response_model=List[ChangeAggregateRead])
def list_change_aggregates(session: Session = Depends(get_session)):
    """List all change aggregates."""
    outputs = session.exec(select(ChangeAggregate)).all()
    return outputs


@router.get("/{output_id}", response_model=ChangeAggregateRead)
def get_change_aggregate(output_id: UUID, session: Session = Depends(get_session)):
    """Get a specific change aggregate."""
    output = session.get(ChangeAggregate, output_id)
    if not output:
        raise HTTPException(status_code=404, detail="Change aggregate not found")
    return output
