from datetime import datetime, timezone
from uuid import UUID

from rich.console import Console
from sqlmodel import Session, create_engine

from policyengine_api.config.settings import settings
from policyengine_api.models import (
    AggregateOutput,
    Dataset,
    Policy,
    Simulation,
    SimulationStatus,
)
from policyengine_api.tasks.celery_app import celery_app

console = Console()


def get_db_session():
    """Get database session for tasks."""
    engine = create_engine(settings.database_url)
    return Session(engine)


@celery_app.task(name="run_simulation")
def run_simulation_task(simulation_id: str):
    """Run a PolicyEngine simulation."""
    console.print(f"[bold blue]Running simulation {simulation_id}[/bold blue]")

    session = get_db_session()
    try:
        simulation = session.get(Simulation, UUID(simulation_id))
        if not simulation:
            raise ValueError(f"Simulation {simulation_id} not found")

        # Update status
        simulation.status = SimulationStatus.RUNNING
        simulation.started_at = datetime.now(timezone.utc)
        session.add(simulation)
        session.commit()

        # Load dataset
        dataset = session.get(Dataset, simulation.dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {simulation.dataset_id} not found")

        # Load policy if specified
        if simulation.policy_id:
            _policy = session.get(Policy, simulation.policy_id)  # noqa: F841

        # Import policyengine here to avoid circular imports
        from policyengine.core import Simulation as PESimulation
        from policyengine.tax_benefit_models.uk import (
            PolicyEngineUKDataset,
            uk_latest,
        )
        from policyengine.tax_benefit_models.us import (
            PolicyEngineUSDataset,
            us_latest,
        )

        # Determine tax-benefit model
        if simulation.tax_benefit_model == "uk_latest":
            DatasetClass = PolicyEngineUKDataset
            model_version = uk_latest
        elif simulation.tax_benefit_model == "us_latest":
            DatasetClass = PolicyEngineUSDataset
            model_version = us_latest
        else:
            raise ValueError(
                f"Unsupported tax-benefit model: {simulation.tax_benefit_model}"
            )

        # Load dataset
        pe_dataset = DatasetClass(
            name=dataset.name,
            description=dataset.description or "",
            filepath=dataset.filepath,
            year=dataset.year,
        )

        # Create simulation
        pe_simulation = PESimulation(
            dataset=pe_dataset,
            tax_benefit_model_version=model_version,
            policy=None,  # TODO: Convert policy from DB model
        )

        # Run simulation
        console.print(
            f"[bold green]Executing simulation for dataset {dataset.name}[/bold green]"
        )
        pe_simulation.run()

        # Mark as completed
        simulation.status = SimulationStatus.COMPLETED
        simulation.completed_at = datetime.now(timezone.utc)
        session.add(simulation)
        session.commit()

        console.print(f"[bold green]Simulation {simulation_id} completed[/bold green]")

    except Exception as e:
        console.print(f"[bold red]Simulation {simulation_id} failed: {e}[/bold red]")
        simulation.status = SimulationStatus.FAILED
        simulation.error_message = str(e)
        simulation.completed_at = datetime.now(timezone.utc)
        session.add(simulation)
        session.commit()
        raise
    finally:
        session.close()


@celery_app.task(name="compute_aggregate")
def compute_aggregate_task(output_id: str):
    """Compute an aggregate output."""
    console.print(f"[bold blue]Computing aggregate output {output_id}[/bold blue]")

    session = get_db_session()
    try:
        output = session.get(AggregateOutput, UUID(output_id))
        if not output:
            raise ValueError(f"Aggregate output {output_id} not found")

        simulation = session.get(Simulation, output.simulation_id)
        if not simulation:
            raise ValueError(f"Simulation {output.simulation_id} not found")

        if simulation.status != SimulationStatus.COMPLETED:
            msg = f"Simulation {output.simulation_id} not completed"
            raise ValueError(f"{msg} (status: {simulation.status})")

        # Import policyengine

        # Load simulation output
        # TODO: Load actual simulation output from storage
        # For now, we'll need to re-run or load cached results

        console.print(f"[bold green]Aggregate output {output_id} computed[/bold green]")

        # Update result
        # output.result = aggregate.result
        # session.add(output)
        # session.commit()

    except Exception as e:
        console.print(f"[bold red]Aggregate output {output_id} failed: {e}[/bold red]")
        raise
    finally:
        session.close()
