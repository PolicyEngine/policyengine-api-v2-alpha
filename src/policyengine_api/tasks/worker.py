"""Simple polling worker that processes pending simulations."""

import time
from datetime import datetime, timezone

import logfire
from rich.console import Console
from sqlmodel import Session, create_engine, select

from policyengine_api.config.settings import settings
from policyengine_api.models import Simulation, SimulationStatus

console = Console()


def get_db_session():
    """Get database session."""
    engine = create_engine(settings.database_url)
    return Session(engine)


def run_simulation(simulation_id: str, session: Session):
    """Run a single simulation."""
    from pathlib import Path
    import tempfile
    from uuid import UUID

    from policyengine_api.models import Dataset
    from policyengine_api.services.storage import download_dataset

    with logfire.span("run_simulation", simulation_id=simulation_id):
        console.print(f"[bold blue]Running simulation {simulation_id}[/bold blue]")

        simulation = session.get(Simulation, UUID(simulation_id))
        if not simulation:
            raise ValueError(f"Simulation {simulation_id} not found")

        # Update status to running
        simulation.status = SimulationStatus.RUNNING
        simulation.started_at = datetime.now(timezone.utc)
        session.add(simulation)
        session.commit()

        # Load dataset
        dataset = session.get(Dataset, simulation.dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {simulation.dataset_id} not found")

        # Import policyengine
        from policyengine.core import Simulation as PESimulation
        from policyengine.tax_benefit_models.uk import PolicyEngineUKDataset, uk_latest
        from policyengine.tax_benefit_models.us import PolicyEngineUSDataset, us_latest

        # Determine tax-benefit model
        if simulation.tax_benefit_model == "uk_latest":
            DatasetClass = PolicyEngineUKDataset
            model_version = uk_latest
        elif simulation.tax_benefit_model == "us_latest":
            DatasetClass = PolicyEngineUSDataset
            model_version = us_latest
        else:
            raise ValueError(f"Unsupported model: {simulation.tax_benefit_model}")

        # Download and run
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / dataset.filepath
            console.print(f"  Downloading dataset: {dataset.filepath}")
            download_dataset(dataset.filepath, str(local_path))

            pe_dataset = DatasetClass(
                name=dataset.name,
                description=dataset.description or "",
                filepath=str(local_path),
                year=dataset.year,
            )

            pe_simulation = PESimulation(
                dataset=pe_dataset,
                tax_benefit_model_version=model_version,
                policy=None,
            )

            console.print(f"[green]Executing simulation for {dataset.name}[/green]")
            pe_simulation.run()

        # Mark completed
        simulation.status = SimulationStatus.COMPLETED
        simulation.completed_at = datetime.now(timezone.utc)
        session.add(simulation)
        session.commit()

        console.print(f"[bold green]Simulation {simulation_id} completed[/bold green]")


def process_pending_simulations():
    """Process all pending simulations."""
    session = get_db_session()
    try:
        pending = session.exec(
            select(Simulation).where(Simulation.status == SimulationStatus.PENDING)
        ).all()

        console.print(f"[blue]Found {len(pending)} pending simulations[/blue]")

        for simulation in pending:
            try:
                run_simulation(str(simulation.id), session)
            except Exception as e:
                console.print(f"[red]Simulation {simulation.id} failed: {e}[/red]")
                simulation.status = SimulationStatus.FAILED
                simulation.error_message = str(e)
                simulation.completed_at = datetime.now(timezone.utc)
                session.add(simulation)
                session.commit()
    finally:
        session.close()


def main():
    """Main worker loop."""
    logfire.configure(
        service_name="policyengine-worker",
        token=settings.logfire_token if settings.logfire_token else None,
        environment=settings.logfire_environment,
    )

    console.print("[bold]PolicyEngine Worker starting...[/bold]")
    console.print(f"Poll interval: {settings.worker_poll_interval}s")

    while True:
        try:
            process_pending_simulations()
        except Exception as e:
            console.print(f"[red]Error in worker loop: {e}[/red]")

        time.sleep(settings.worker_poll_interval)


if __name__ == "__main__":
    main()
