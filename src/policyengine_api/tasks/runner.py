from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID
import tempfile

from rich.console import Console
from sqlmodel import Session, create_engine, select
import logfire

from policyengine_api.config.settings import settings
from policyengine_api.models import (
    AggregateOutput,
    Dataset,
    Policy,
    Simulation,
    SimulationStatus,
)
from policyengine_api.services.storage import download_dataset, upload_dataset
from policyengine_api.tasks.celery_app import celery_app

console = Console()
logfire.configure()


def get_db_session():
    """Get database session for tasks."""
    engine = create_engine(settings.database_url)
    return Session(engine)


@celery_app.task(name="run_simulation")
def run_simulation_task(simulation_id: str):
    """Run a PolicyEngine simulation."""
    with logfire.span("run_simulation", simulation_id=simulation_id):
        console.print(f"[bold blue]Running simulation {simulation_id}[/bold blue]")

        session = get_db_session()
        try:
            with logfire.span("load_simulation_record"):
                simulation = session.get(Simulation, UUID(simulation_id))
                if not simulation:
                    raise ValueError(f"Simulation {simulation_id} not found")

            with logfire.span("update_status_to_running"):
                # Update status
                simulation.status = SimulationStatus.RUNNING
                simulation.started_at = datetime.now(timezone.utc)
                session.add(simulation)
                session.commit()

            with logfire.span("load_dataset_record"):
                # Load dataset
                dataset = session.get(Dataset, simulation.dataset_id)
                if not dataset:
                    raise ValueError(f"Dataset {simulation.dataset_id} not found")

            with logfire.span("load_policy_if_specified"):
                # Load policy if specified
                if simulation.policy_id:
                    _policy = session.get(Policy, simulation.policy_id)  # noqa: F841

            with logfire.span("import_policyengine_modules"):
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

            with logfire.span("determine_tax_benefit_model"):
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

            # Download dataset from S3 to temp file
            with logfire.span("download_dataset_from_s3"):
                with tempfile.TemporaryDirectory() as tmpdir:
                    local_path = Path(tmpdir) / dataset.filepath
                    console.print(f"  Downloading dataset from S3: {dataset.filepath}")
                    download_dataset(dataset.filepath, str(local_path))

                    with logfire.span("load_dataset_into_memory"):
                        # Load dataset
                        pe_dataset = DatasetClass(
                            name=dataset.name,
                            description=dataset.description or "",
                            filepath=str(local_path),
                            year=dataset.year,
                        )

                    with logfire.span("create_simulation_object"):
                        # Create simulation
                        pe_simulation = PESimulation(
                            dataset=pe_dataset,
                            tax_benefit_model_version=model_version,
                            policy=None,  # TODO: Convert policy from DB model
                        )

                    with logfire.span("execute_simulation"):
                        # Run simulation
                        console.print(
                            f"[bold green]Executing simulation for dataset {dataset.name}[/bold green]"
                        )
                        pe_simulation.run()

                    # TODO: Upload simulation results to S3
                    with logfire.span("upload_simulation_results"):
                        # For now, we just mark as completed
                        # In the future, save output dataset to S3
                        pass

            with logfire.span("mark_simulation_completed"):
                # Mark as completed
                simulation.status = SimulationStatus.COMPLETED
                simulation.completed_at = datetime.now(timezone.utc)
                session.add(simulation)
                session.commit()

            console.print(f"[bold green]Simulation {simulation_id} completed[/bold green]")

        except Exception as e:
            with logfire.span("handle_simulation_failure"):
                console.print(f"[bold red]Simulation {simulation_id} failed: {e}[/bold red]")
                simulation.status = SimulationStatus.FAILED
                simulation.error_message = str(e)
                simulation.completed_at = datetime.now(timezone.utc)
                session.add(simulation)
                session.commit()
            raise
        finally:
            session.close()


@celery_app.task(name="scan_pending_simulations")
def scan_pending_simulations():
    """Scan for pending simulations and queue them for execution."""
    with logfire.span("scan_pending_simulations"):
        session = get_db_session()
        try:
            with logfire.span("query_pending_simulations"):
                # Find all pending simulations
                pending_simulations = session.exec(
                    select(Simulation).where(Simulation.status == SimulationStatus.PENDING)
                ).all()

                console.print(f"[bold blue]Found {len(pending_simulations)} pending simulations[/bold blue]")

            with logfire.span("queue_pending_simulations"):
                # Queue each pending simulation
                for simulation in pending_simulations:
                    with logfire.span(f"queue_simulation_{simulation.id}"):
                        console.print(f"  Queueing simulation {simulation.id}")
                        run_simulation_task.delay(str(simulation.id))

                console.print(f"[green]✓[/green] Queued {len(pending_simulations)} simulations")

        except Exception as e:
            console.print(f"[bold red]Failed to scan pending simulations: {e}[/bold red]")
            raise
        finally:
            session.close()


@celery_app.task(name="compute_aggregate")
def compute_aggregate_task(output_id: str):
    """Compute an aggregate output."""
    with logfire.span("compute_aggregate", output_id=output_id):
        console.print(f"[bold blue]Computing aggregate output {output_id}[/bold blue]")

        session = get_db_session()
        try:
            with logfire.span("load_output_record"):
                output = session.get(AggregateOutput, UUID(output_id))
                if not output:
                    raise ValueError(f"Aggregate output {output_id} not found")

            with logfire.span("load_simulation_record"):
                simulation = session.get(Simulation, output.simulation_id)
                if not simulation:
                    raise ValueError(f"Simulation {output.simulation_id} not found")

            with logfire.span("check_simulation_status"):
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
