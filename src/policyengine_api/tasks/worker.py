"""Simple polling worker that processes pending simulations and reports."""

import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID

from fastapi import FastAPI
from rich.console import Console
from sqlmodel import Session, create_engine, select

from policyengine_api.config.settings import settings
from policyengine_api.models import (
    Dataset,
    DecileImpact,
    Dynamic,
    Policy,
    ProgramStatistics,
    Report,
    ReportStatus,
    Simulation,
    SimulationStatus,
    TaxBenefitModel,
    TaxBenefitModelVersion,
)
from policyengine_api.services.storage import download_dataset

console = Console()
worker_thread: threading.Thread | None = None


def get_db_session():
    """Get database session."""
    engine = create_engine(settings.database_url)
    return Session(engine)


def _get_pe_policy(policy_id: UUID | None, model_version, session: Session):
    """Convert database Policy to policyengine Policy."""
    if policy_id is None:
        return None

    from policyengine.core.policy import ParameterValue as PEParameterValue
    from policyengine.core.policy import Policy as PEPolicy

    db_policy = session.get(Policy, policy_id)
    if not db_policy:
        return None

    param_lookup = {p.name: p for p in model_version.parameters}

    pe_param_values = []
    for pv in db_policy.parameter_values:
        if not pv.parameter:
            continue
        pe_param = param_lookup.get(pv.parameter.name)
        if not pe_param:
            continue
        pe_pv = PEParameterValue(
            parameter=pe_param,
            value=pv.value_json.get("value")
            if isinstance(pv.value_json, dict)
            else pv.value_json,
            start_date=pv.start_date,
            end_date=pv.end_date,
        )
        pe_param_values.append(pe_pv)

    return PEPolicy(
        name=db_policy.name,
        description=db_policy.description,
        parameter_values=pe_param_values,
    )


def _get_pe_dynamic(dynamic_id: UUID | None, model_version, session: Session):
    """Convert database Dynamic to policyengine Dynamic."""
    if dynamic_id is None:
        return None

    from policyengine.core.dynamic import Dynamic as PEDynamic
    from policyengine.core.policy import ParameterValue as PEParameterValue

    db_dynamic = session.get(Dynamic, dynamic_id)
    if not db_dynamic:
        return None

    param_lookup = {p.name: p for p in model_version.parameters}

    pe_param_values = []
    for pv in db_dynamic.parameter_values:
        if not pv.parameter:
            continue
        pe_param = param_lookup.get(pv.parameter.name)
        if not pe_param:
            continue
        pe_pv = PEParameterValue(
            parameter=pe_param,
            value=pv.value_json.get("value")
            if isinstance(pv.value_json, dict)
            else pv.value_json,
            start_date=pv.start_date,
            end_date=pv.end_date,
        )
        pe_param_values.append(pe_pv)

    return PEDynamic(
        name=db_dynamic.name,
        description=db_dynamic.description,
        parameter_values=pe_param_values,
    )


def run_simulation(simulation_id: str, session: Session):
    """Run a single simulation."""
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

    # Get model version
    model_version = session.get(TaxBenefitModelVersion, simulation.tax_benefit_model_version_id)
    if not model_version:
        raise ValueError(f"Model version {simulation.tax_benefit_model_version_id} not found")

    # Load the model version's model to determine UK vs US
    tax_benefit_model = session.get(TaxBenefitModel, model_version.model_id)
    if not tax_benefit_model:
        raise ValueError(f"Model {model_version.model_id} not found")

    # Import policyengine
    from policyengine.core import Simulation as PESimulation

    # Determine dataset class and model version based on model name
    if tax_benefit_model.name == "policyengine-uk":
        from policyengine.tax_benefit_models.uk import uk_latest
        from policyengine.tax_benefit_models.uk.datasets import PolicyEngineUKDataset
        DatasetClass = PolicyEngineUKDataset
        pe_model_version = uk_latest
    elif tax_benefit_model.name == "policyengine-us":
        from policyengine.tax_benefit_models.us import us_latest
        from policyengine.tax_benefit_models.us.datasets import PolicyEngineUSDataset
        DatasetClass = PolicyEngineUSDataset
        pe_model_version = us_latest
    else:
        raise ValueError(f"Unsupported model: {tax_benefit_model.name}")

    # Get policy and dynamic if specified
    policy = _get_pe_policy(simulation.policy_id, pe_model_version, session)
    dynamic = _get_pe_dynamic(simulation.dynamic_id, pe_model_version, session)

    # Download dataset (uses cache)
    console.print(f"  Loading dataset: {dataset.filepath}")
    local_path = download_dataset(dataset.filepath)

    pe_dataset = DatasetClass(
        name=dataset.name,
        description=dataset.description or "",
        filepath=local_path,
        year=dataset.year,
    )

    console.print(f"  Creating simulation with policy={policy is not None}, dynamic={dynamic is not None}")
    PESimulation(
        dataset=pe_dataset,
        tax_benefit_model_version=pe_model_version,
        policy=policy,
        dynamic=dynamic,
    )

    # Mark completed (simulation is lazy - calculations happen on access)
    simulation.status = SimulationStatus.COMPLETED
    simulation.completed_at = datetime.now(timezone.utc)
    session.add(simulation)
    session.commit()

    console.print(f"[bold green]Simulation {simulation_id} completed[/bold green]")


def run_report(report_id: str, session: Session):
    """Run economic impact analysis for a report."""
    console.print(f"[bold blue]Running report {report_id}[/bold blue]")

    report = session.get(Report, UUID(report_id))
    if not report:
        raise ValueError(f"Report {report_id} not found")

    # Check both simulations are complete
    baseline_sim = session.get(Simulation, report.baseline_simulation_id)
    reform_sim = session.get(Simulation, report.reform_simulation_id)

    if not baseline_sim or baseline_sim.status != SimulationStatus.COMPLETED:
        console.print("  Baseline simulation not ready, skipping")
        return
    if not reform_sim or reform_sim.status != SimulationStatus.COMPLETED:
        console.print("  Reform simulation not ready, skipping")
        return

    # Update status to running
    report.status = ReportStatus.RUNNING
    session.add(report)
    session.commit()

    # Get dataset
    dataset = session.get(Dataset, baseline_sim.dataset_id)
    if not dataset:
        raise ValueError(f"Dataset {baseline_sim.dataset_id} not found")

    # Get model version
    model_version = session.get(TaxBenefitModelVersion, baseline_sim.tax_benefit_model_version_id)
    if not model_version:
        raise ValueError("Model version not found")

    tax_benefit_model = session.get(TaxBenefitModel, model_version.model_id)
    if not tax_benefit_model:
        raise ValueError("Tax benefit model not found")

    # Import and setup
    from policyengine.core import Simulation as PESimulation

    if tax_benefit_model.name == "policyengine-uk":
        from policyengine.tax_benefit_models.uk import uk_latest
        from policyengine.tax_benefit_models.uk.datasets import PolicyEngineUKDataset
        DatasetClass = PolicyEngineUKDataset
        pe_model_version = uk_latest
        is_uk = True
    else:
        from policyengine.tax_benefit_models.us import us_latest
        from policyengine.tax_benefit_models.us.datasets import PolicyEngineUSDataset
        DatasetClass = PolicyEngineUSDataset
        pe_model_version = us_latest
        is_uk = False

    # Get policies and dynamics
    baseline_policy = _get_pe_policy(baseline_sim.policy_id, pe_model_version, session)
    reform_policy = _get_pe_policy(reform_sim.policy_id, pe_model_version, session)
    baseline_dynamic = _get_pe_dynamic(baseline_sim.dynamic_id, pe_model_version, session)
    reform_dynamic = _get_pe_dynamic(reform_sim.dynamic_id, pe_model_version, session)

    # Load dataset (uses cache)
    console.print(f"  Loading dataset: {dataset.filepath}")
    local_path = download_dataset(dataset.filepath)

    pe_dataset = DatasetClass(
        name=dataset.name,
        description=dataset.description or "",
        filepath=local_path,
        year=dataset.year,
    )

    console.print("  Creating simulations...")
    pe_baseline_sim = PESimulation(
        dataset=pe_dataset,
        tax_benefit_model_version=pe_model_version,
        policy=baseline_policy,
        dynamic=baseline_dynamic,
    )
    console.print("  Running baseline simulation...")
    pe_baseline_sim.ensure()

    pe_reform_sim = PESimulation(
        dataset=pe_dataset,
        tax_benefit_model_version=pe_model_version,
        policy=reform_policy,
        dynamic=reform_dynamic,
    )
    console.print("  Running reform simulation...")
    pe_reform_sim.ensure()

    console.print("  Running analysis...")

    # Calculate decile impacts directly (bypassing calculate_decile_impacts which has a bug)
    from policyengine.outputs import DecileImpact as PEDecileImpact

    decile_results = []
    for decile_num in range(1, 11):
        di = PEDecileImpact(
            baseline_simulation=pe_baseline_sim,
            reform_simulation=pe_reform_sim,
            decile=decile_num,
        )
        di.run()
        decile_results.append(di)

    # Store decile impacts
    console.print("  Storing decile impacts...")
    for di in decile_results:
        decile_impact = DecileImpact(
            baseline_simulation_id=baseline_sim.id,
            reform_simulation_id=reform_sim.id,
            report_id=report.id,
            income_variable=di.income_variable,
            entity=di.entity,
            decile=di.decile,
            quantiles=di.quantiles,
            baseline_mean=di.baseline_mean,
            reform_mean=di.reform_mean,
            absolute_change=di.absolute_change,
            relative_change=di.relative_change,
            count_better_off=di.count_better_off,
            count_worse_off=di.count_worse_off,
            count_no_change=di.count_no_change,
        )
        session.add(decile_impact)

    # Store program statistics
    console.print("  Storing program statistics...")

    # Define programs to analyse
    if is_uk:
        from policyengine.core import Simulation as PESimClass
        from policyengine.tax_benefit_models.uk.outputs import ProgrammeStatistics as PEProgrammeStats
        PEProgrammeStats.model_rebuild(_types_namespace={"Simulation": PESimClass})

        programmes = {
            "income_tax": {"entity": "person", "is_tax": True},
            "national_insurance": {"entity": "person", "is_tax": True},
            "vat": {"entity": "household", "is_tax": True},
            "council_tax": {"entity": "household", "is_tax": True},
            "universal_credit": {"entity": "person", "is_tax": False},
            "child_benefit": {"entity": "person", "is_tax": False},
            "pension_credit": {"entity": "person", "is_tax": False},
            "income_support": {"entity": "person", "is_tax": False},
            "working_tax_credit": {"entity": "person", "is_tax": False},
            "child_tax_credit": {"entity": "person", "is_tax": False},
        }

        for prog_name, prog_info in programmes.items():
            try:
                ps = PEProgrammeStats(
                    baseline_simulation=pe_baseline_sim,
                    reform_simulation=pe_reform_sim,
                    programme_name=prog_name,
                    entity=prog_info["entity"],
                    is_tax=prog_info["is_tax"],
                )
                ps.run()
                program_stat = ProgramStatistics(
                    baseline_simulation_id=baseline_sim.id,
                    reform_simulation_id=reform_sim.id,
                    report_id=report.id,
                    program_name=prog_name,
                    entity=prog_info["entity"],
                    is_tax=prog_info["is_tax"],
                    baseline_total=ps.baseline_total,
                    reform_total=ps.reform_total,
                    change=ps.change,
                    baseline_count=ps.baseline_count,
                    reform_count=ps.reform_count,
                    winners=ps.winners,
                    losers=ps.losers,
                )
                session.add(program_stat)
            except KeyError as e:
                console.print(f"    Skipping {prog_name}: variable not found ({e})")
    else:
        from policyengine.core import Simulation as PESimClass
        from policyengine.tax_benefit_models.us.outputs import ProgramStatistics as PEProgramStats
        PEProgramStats.model_rebuild(_types_namespace={"Simulation": PESimClass})

        programs = {
            "income_tax": {"entity": "tax_unit", "is_tax": True},
            "employee_payroll_tax": {"entity": "person", "is_tax": True},
            "snap": {"entity": "spm_unit", "is_tax": False},
            "tanf": {"entity": "spm_unit", "is_tax": False},
            "ssi": {"entity": "spm_unit", "is_tax": False},
            "social_security": {"entity": "person", "is_tax": False},
        }

        for prog_name, prog_info in programs.items():
            try:
                ps = PEProgramStats(
                    baseline_simulation=pe_baseline_sim,
                    reform_simulation=pe_reform_sim,
                    program_name=prog_name,
                    entity=prog_info["entity"],
                    is_tax=prog_info["is_tax"],
                )
                ps.run()
                program_stat = ProgramStatistics(
                    baseline_simulation_id=baseline_sim.id,
                    reform_simulation_id=reform_sim.id,
                    report_id=report.id,
                    program_name=prog_name,
                    entity=prog_info["entity"],
                    is_tax=prog_info["is_tax"],
                    baseline_total=ps.baseline_total,
                    reform_total=ps.reform_total,
                    change=ps.change,
                    baseline_count=ps.baseline_count,
                    reform_count=ps.reform_count,
                    winners=ps.winners,
                    losers=ps.losers,
                )
                session.add(program_stat)
            except KeyError as e:
                console.print(f"    Skipping {prog_name}: variable not found ({e})")

    # Mark report as completed
    report.status = ReportStatus.COMPLETED
    session.add(report)
    session.commit()

    console.print(f"[bold green]Report {report_id} completed[/bold green]")


def process_pending_work():
    """Process all pending simulations and reports."""
    session = get_db_session()
    try:
        # Process pending simulations
        pending_sims = session.exec(
            select(Simulation).where(Simulation.status == SimulationStatus.PENDING)
        ).all()

        if pending_sims:
            console.print(f"[blue]Found {len(pending_sims)} pending simulations[/blue]")

        for simulation in pending_sims:
            try:
                run_simulation(str(simulation.id), session)
            except Exception as e:
                console.print(f"[red]Simulation {simulation.id} failed: {e}[/red]")
                simulation.status = SimulationStatus.FAILED
                simulation.error_message = str(e)
                simulation.completed_at = datetime.now(timezone.utc)
                session.add(simulation)
                session.commit()

        # Process pending reports (only if both simulations are complete)
        pending_reports = session.exec(
            select(Report).where(Report.status == ReportStatus.PENDING)
        ).all()

        if pending_reports:
            console.print(f"[blue]Found {len(pending_reports)} pending reports[/blue]")

        for report in pending_reports:
            try:
                run_report(str(report.id), session)
            except Exception as e:
                console.print(f"[red]Report {report.id} failed: {e}[/red]")
                report.status = ReportStatus.FAILED
                report.error_message = str(e)
                session.add(report)
                session.commit()

    finally:
        session.close()


def worker_loop():
    """Background worker loop."""
    console.print("[bold]PolicyEngine Worker loop starting...[/bold]")
    console.print(f"Poll interval: {settings.worker_poll_interval}s")

    while True:
        try:
            process_pending_work()
        except Exception as e:
            console.print(f"[red]Error in worker loop: {e}[/red]")

        time.sleep(settings.worker_poll_interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start worker thread on startup."""
    global worker_thread
    console.print("[bold green]Starting worker thread...[/bold green]")
    worker_thread = threading.Thread(target=worker_loop, daemon=True)
    worker_thread.start()
    yield
    console.print("[bold yellow]Worker shutting down...[/bold yellow]")


app = FastAPI(title="PolicyEngine Worker", lifespan=lifespan)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "worker_alive": worker_thread is not None and worker_thread.is_alive(),
    }


def main():
    """Run worker as HTTP service."""
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(settings.worker_port),
    )


if __name__ == "__main__":
    main()
