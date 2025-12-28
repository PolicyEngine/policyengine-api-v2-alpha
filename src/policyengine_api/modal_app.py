"""Modal.com serverless functions for PolicyEngine compute.

This module defines Modal functions for running PolicyEngine simulations
with sub-1s cold starts via memory snapshot restore. The heavy policyengine
imports happen at image build time, not runtime.

Deploy with: modal deploy src/policyengine_api/modal_app.py
"""

import modal

# Base image with common dependencies using uv for fast installs
base_image = (
    modal.Image.debian_slim(python_version="3.13")
    .apt_install("libhdf5-dev")
    .pip_install("uv")
    .run_commands(
        "uv pip install --system "
        "policyengine>=3.1.15 "
        "sqlmodel>=0.0.22 "
        "psycopg2-binary>=2.9.10 "
        "supabase>=2.10.0 "
        "rich>=13.9.4"
    )
)


def _import_uk():
    """Import UK model at build time to snapshot in memory."""
    from policyengine.tax_benefit_models.uk import uk_latest  # noqa: F401
    print("UK model loaded and snapshotted")


def _import_us():
    """Import US model at build time to snapshot in memory."""
    from policyengine.tax_benefit_models.us import us_latest  # noqa: F401
    print("US model loaded and snapshotted")


# UK image - uses run_function to snapshot imported modules in memory
uk_image = (
    base_image
    .run_commands("uv pip install --system policyengine-uk>=2.0.0")
    .run_function(_import_uk)
)

# US image - uses run_function to snapshot imported modules in memory
us_image = (
    base_image
    .run_commands("uv pip install --system policyengine-us>=1.0.0")
    .run_function(_import_us)
)

app = modal.App("policyengine")


# Secrets for database access
secrets = modal.Secret.from_name("policyengine-db")


def get_db_session(database_url: str):
    """Create database session."""
    from sqlmodel import Session, create_engine

    engine = create_engine(database_url)
    return Session(engine)


def download_dataset(
    filepath: str, supabase_url: str, supabase_key: str, storage_bucket: str
) -> str:
    """Download dataset from Supabase storage."""
    from pathlib import Path

    from supabase import create_client

    cache_dir = Path("/tmp/policyengine_dataset_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / filepath

    if cache_path.exists():
        return str(cache_path)

    client = create_client(supabase_url, supabase_key)
    data = client.storage.from_(storage_bucket).download(filepath)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "wb") as f:
        f.write(data)

    return str(cache_path)


@app.function(image=uk_image, secrets=[secrets], memory=4096, timeout=600)
def calculate_household_uk(
    job_id: str,
    people: list[dict],
    benunit: dict,
    household: dict,
    year: int,
    policy_data: dict | None,
    dynamic_data: dict | None,
) -> None:
    """Calculate UK household and write result to database."""
    import json
    import os
    from datetime import datetime, timezone

    from rich.console import Console
    from sqlmodel import Session, create_engine

    console = Console()
    console.print(f"[bold blue]Running UK household job {job_id}[/bold blue]")

    database_url = os.environ["DATABASE_URL"]
    engine = create_engine(database_url)

    try:
        from policyengine.tax_benefit_models.uk import uk_latest
        from policyengine.tax_benefit_models.uk.analysis import (
            UKHouseholdInput,
            calculate_household_impact,
        )

        # Build policy if provided
        policy = None
        if policy_data:
            from policyengine.core.policy import (
                ParameterValue as PEParameterValue,
            )
            from policyengine.core.policy import (
                Policy as PEPolicy,
            )

            pe_param_values = []
            param_lookup = {p.name: p for p in uk_latest.parameters}
            for pv in policy_data.get("parameter_values", []):
                pe_param = param_lookup.get(pv["parameter_name"])
                if pe_param:
                    pe_pv = PEParameterValue(
                        parameter=pe_param,
                        value=pv["value"],
                        start_date=datetime.fromisoformat(pv["start_date"])
                        if pv.get("start_date")
                        else None,
                        end_date=datetime.fromisoformat(pv["end_date"])
                        if pv.get("end_date")
                        else None,
                    )
                    pe_param_values.append(pe_pv)
            policy = PEPolicy(
                name=policy_data.get("name", ""),
                description=policy_data.get("description", ""),
                parameter_values=pe_param_values,
            )

        pe_input = UKHouseholdInput(
            people=people,
            benunit=benunit,
            household=household,
            year=year,
        )

        result = calculate_household_impact(pe_input, policy=policy)

        # Write result to database
        with Session(engine) as session:
            from sqlmodel import text

            session.exec(
                text("""
                    UPDATE household_jobs
                    SET status = 'completed',
                        result = :result,
                        completed_at = :completed_at
                    WHERE id = :job_id
                """),
                params={
                    "job_id": job_id,
                    "result": json.dumps(
                        {
                            "person": result.person,
                            "benunit": result.benunit,
                            "household": result.household,
                        }
                    ),
                    "completed_at": datetime.now(timezone.utc),
                },
            )
            session.commit()

        console.print(f"[bold green]UK household job {job_id} completed[/bold green]")

    except Exception as e:
        console.print(f"[bold red]UK household job {job_id} failed: {e}[/bold red]")
        with Session(engine) as session:
            from sqlmodel import text

            session.exec(
                text("""
                    UPDATE household_jobs
                    SET status = 'failed',
                        error_message = :error,
                        completed_at = :completed_at
                    WHERE id = :job_id
                """),
                params={
                    "job_id": job_id,
                    "error": str(e),
                    "completed_at": datetime.now(timezone.utc),
                },
            )
            session.commit()
        raise


@app.function(image=us_image, secrets=[secrets], memory=4096, timeout=600)
def calculate_household_us(
    job_id: str,
    people: list[dict],
    marital_unit: dict,
    family: dict,
    spm_unit: dict,
    tax_unit: dict,
    household: dict,
    year: int,
    policy_data: dict | None,
    dynamic_data: dict | None,
) -> None:
    """Calculate US household and write result to database."""
    import json
    import os
    from datetime import datetime, timezone

    from rich.console import Console
    from sqlmodel import Session, create_engine

    console = Console()
    console.print(f"[bold blue]Running US household job {job_id}[/bold blue]")

    database_url = os.environ["DATABASE_URL"]
    engine = create_engine(database_url)

    try:
        from policyengine.tax_benefit_models.us import us_latest
        from policyengine.tax_benefit_models.us.analysis import (
            USHouseholdInput,
            calculate_household_impact,
        )

        # Build policy if provided
        policy = None
        if policy_data:
            from policyengine.core.policy import (
                ParameterValue as PEParameterValue,
            )
            from policyengine.core.policy import (
                Policy as PEPolicy,
            )

            pe_param_values = []
            param_lookup = {p.name: p for p in us_latest.parameters}
            for pv in policy_data.get("parameter_values", []):
                pe_param = param_lookup.get(pv["parameter_name"])
                if pe_param:
                    pe_pv = PEParameterValue(
                        parameter=pe_param,
                        value=pv["value"],
                        start_date=datetime.fromisoformat(pv["start_date"])
                        if pv.get("start_date")
                        else None,
                        end_date=datetime.fromisoformat(pv["end_date"])
                        if pv.get("end_date")
                        else None,
                    )
                    pe_param_values.append(pe_pv)
            policy = PEPolicy(
                name=policy_data.get("name", ""),
                description=policy_data.get("description", ""),
                parameter_values=pe_param_values,
            )

        pe_input = USHouseholdInput(
            people=people,
            marital_unit=marital_unit,
            family=family,
            spm_unit=spm_unit,
            tax_unit=tax_unit,
            household=household,
            year=year,
        )

        result = calculate_household_impact(pe_input, policy=policy)

        # Write result to database
        with Session(engine) as session:
            from sqlmodel import text

            session.exec(
                text("""
                    UPDATE household_jobs
                    SET status = 'completed',
                        result = :result,
                        completed_at = :completed_at
                    WHERE id = :job_id
                """),
                params={
                    "job_id": job_id,
                    "result": json.dumps(
                        {
                            "person": result.person,
                            "marital_unit": result.marital_unit,
                            "family": result.family,
                            "spm_unit": result.spm_unit,
                            "tax_unit": result.tax_unit,
                            "household": result.household,
                        }
                    ),
                    "completed_at": datetime.now(timezone.utc),
                },
            )
            session.commit()

        console.print(f"[bold green]US household job {job_id} completed[/bold green]")

    except Exception as e:
        console.print(f"[bold red]US household job {job_id} failed: {e}[/bold red]")
        with Session(engine) as session:
            from sqlmodel import text

            session.exec(
                text("""
                    UPDATE household_jobs
                    SET status = 'failed',
                        error_message = :error,
                        completed_at = :completed_at
                    WHERE id = :job_id
                """),
                params={
                    "job_id": job_id,
                    "error": str(e),
                    "completed_at": datetime.now(timezone.utc),
                },
            )
            session.commit()
        raise


@app.function(image=uk_image, secrets=[secrets], memory=8192, timeout=1800)
def run_report_uk(report_id: str) -> None:
    """Run UK economic impact report and write results to database."""
    import os
    from datetime import datetime, timezone
    from uuid import UUID

    from rich.console import Console
    from sqlmodel import Session, create_engine

    console = Console()
    console.print(f"[bold blue]Running UK report {report_id}[/bold blue]")

    database_url = os.environ["DATABASE_URL"]
    supabase_url = os.environ["SUPABASE_URL"]
    supabase_key = os.environ["SUPABASE_KEY"]
    storage_bucket = os.environ.get("STORAGE_BUCKET", "datasets")

    engine = create_engine(database_url)

    # Import models inline to avoid import issues
    from policyengine_api.models import (
        Dataset,
        DecileImpact,
        ProgramStatistics,
        Report,
        ReportStatus,
        Simulation,
        SimulationStatus,
        TaxBenefitModelVersion,
    )

    try:
        with Session(engine) as session:
            # Load report and related data
            report = session.get(Report, UUID(report_id))
            if not report:
                raise ValueError(f"Report {report_id} not found")

            baseline_sim = session.get(Simulation, report.baseline_simulation_id)
            reform_sim = session.get(Simulation, report.reform_simulation_id)

            if not baseline_sim or not reform_sim:
                raise ValueError("Simulations not found")

            # Update status to running
            report.status = ReportStatus.RUNNING
            session.add(report)
            session.commit()

            # Get dataset
            dataset = session.get(Dataset, baseline_sim.dataset_id)
            if not dataset:
                raise ValueError(f"Dataset {baseline_sim.dataset_id} not found")

            # Get model version (unused but keeping for reference)
            _ = session.get(
                TaxBenefitModelVersion, baseline_sim.tax_benefit_model_version_id
            )

            # Import policyengine
            from policyengine.core import Simulation as PESimulation
            from policyengine.outputs import DecileImpact as PEDecileImpact
            from policyengine.tax_benefit_models.uk import uk_latest
            from policyengine.tax_benefit_models.uk.datasets import (
                PolicyEngineUKDataset,
            )
            from policyengine.tax_benefit_models.uk.outputs import (
                ProgrammeStatistics as PEProgrammeStats,
            )

            pe_model_version = uk_latest

            # Get policies
            baseline_policy = _get_pe_policy_uk(
                baseline_sim.policy_id, pe_model_version, session
            )
            reform_policy = _get_pe_policy_uk(
                reform_sim.policy_id, pe_model_version, session
            )
            baseline_dynamic = _get_pe_dynamic_uk(
                baseline_sim.dynamic_id, pe_model_version, session
            )
            reform_dynamic = _get_pe_dynamic_uk(
                reform_sim.dynamic_id, pe_model_version, session
            )

            # Download dataset
            console.print(f"  Loading dataset: {dataset.filepath}")
            local_path = download_dataset(
                dataset.filepath, supabase_url, supabase_key, storage_bucket
            )

            pe_dataset = PolicyEngineUKDataset(
                name=dataset.name,
                description=dataset.description or "",
                filepath=local_path,
                year=dataset.year,
            )

            # Create and run simulations
            console.print("  Running baseline simulation...")
            pe_baseline_sim = PESimulation(
                dataset=pe_dataset,
                tax_benefit_model_version=pe_model_version,
                policy=baseline_policy,
                dynamic=baseline_dynamic,
            )
            pe_baseline_sim.ensure()

            console.print("  Running reform simulation...")
            pe_reform_sim = PESimulation(
                dataset=pe_dataset,
                tax_benefit_model_version=pe_model_version,
                policy=reform_policy,
                dynamic=reform_dynamic,
            )
            pe_reform_sim.ensure()

            # Calculate decile impacts
            console.print("  Calculating decile impacts...")
            for decile_num in range(1, 11):
                di = PEDecileImpact(
                    baseline_simulation=pe_baseline_sim,
                    reform_simulation=pe_reform_sim,
                    decile=decile_num,
                )
                di.run()

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

            # Calculate program statistics
            console.print("  Calculating program statistics...")
            PEProgrammeStats.model_rebuild(
                _types_namespace={"Simulation": PESimulation}
            )

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

            # Mark simulations and report as completed
            baseline_sim.status = SimulationStatus.COMPLETED
            baseline_sim.completed_at = datetime.now(timezone.utc)
            reform_sim.status = SimulationStatus.COMPLETED
            reform_sim.completed_at = datetime.now(timezone.utc)
            report.status = ReportStatus.COMPLETED

            session.add(baseline_sim)
            session.add(reform_sim)
            session.add(report)
            session.commit()

        console.print(f"[bold green]UK report {report_id} completed[/bold green]")

    except Exception as e:
        console.print(f"[bold red]UK report {report_id} failed: {e}[/bold red]")
        with Session(engine) as session:
            report = session.get(Report, UUID(report_id))
            if report:
                report.status = ReportStatus.FAILED
                report.error_message = str(e)
                session.add(report)
                session.commit()
        raise


@app.function(image=us_image, secrets=[secrets], memory=8192, timeout=1800)
def run_report_us(report_id: str) -> None:
    """Run US economic impact report and write results to database."""
    import os
    from datetime import datetime, timezone
    from uuid import UUID

    from rich.console import Console
    from sqlmodel import Session, create_engine

    console = Console()
    console.print(f"[bold blue]Running US report {report_id}[/bold blue]")

    database_url = os.environ["DATABASE_URL"]
    supabase_url = os.environ["SUPABASE_URL"]
    supabase_key = os.environ["SUPABASE_KEY"]
    storage_bucket = os.environ.get("STORAGE_BUCKET", "datasets")

    engine = create_engine(database_url)

    # Import models inline
    from policyengine_api.models import (
        Dataset,
        DecileImpact,
        ProgramStatistics,
        Report,
        ReportStatus,
        Simulation,
        SimulationStatus,
    )

    try:
        with Session(engine) as session:
            # Load report and related data
            report = session.get(Report, UUID(report_id))
            if not report:
                raise ValueError(f"Report {report_id} not found")

            baseline_sim = session.get(Simulation, report.baseline_simulation_id)
            reform_sim = session.get(Simulation, report.reform_simulation_id)

            if not baseline_sim or not reform_sim:
                raise ValueError("Simulations not found")

            # Update status to running
            report.status = ReportStatus.RUNNING
            session.add(report)
            session.commit()

            # Get dataset
            dataset = session.get(Dataset, baseline_sim.dataset_id)
            if not dataset:
                raise ValueError(f"Dataset {baseline_sim.dataset_id} not found")

            # Import policyengine
            from policyengine.core import Simulation as PESimulation
            from policyengine.outputs import DecileImpact as PEDecileImpact
            from policyengine.tax_benefit_models.us import us_latest
            from policyengine.tax_benefit_models.us.datasets import (
                PolicyEngineUSDataset,
            )
            from policyengine.tax_benefit_models.us.outputs import (
                ProgramStatistics as PEProgramStats,
            )

            pe_model_version = us_latest

            # Get policies
            baseline_policy = _get_pe_policy_us(
                baseline_sim.policy_id, pe_model_version, session
            )
            reform_policy = _get_pe_policy_us(
                reform_sim.policy_id, pe_model_version, session
            )
            baseline_dynamic = _get_pe_dynamic_us(
                baseline_sim.dynamic_id, pe_model_version, session
            )
            reform_dynamic = _get_pe_dynamic_us(
                reform_sim.dynamic_id, pe_model_version, session
            )

            # Download dataset
            console.print(f"  Loading dataset: {dataset.filepath}")
            local_path = download_dataset(
                dataset.filepath, supabase_url, supabase_key, storage_bucket
            )

            pe_dataset = PolicyEngineUSDataset(
                name=dataset.name,
                description=dataset.description or "",
                filepath=local_path,
                year=dataset.year,
            )

            # Create and run simulations
            console.print("  Running baseline simulation...")
            pe_baseline_sim = PESimulation(
                dataset=pe_dataset,
                tax_benefit_model_version=pe_model_version,
                policy=baseline_policy,
                dynamic=baseline_dynamic,
            )
            pe_baseline_sim.ensure()

            console.print("  Running reform simulation...")
            pe_reform_sim = PESimulation(
                dataset=pe_dataset,
                tax_benefit_model_version=pe_model_version,
                policy=reform_policy,
                dynamic=reform_dynamic,
            )
            pe_reform_sim.ensure()

            # Calculate decile impacts
            console.print("  Calculating decile impacts...")
            for decile_num in range(1, 11):
                di = PEDecileImpact(
                    baseline_simulation=pe_baseline_sim,
                    reform_simulation=pe_reform_sim,
                    decile=decile_num,
                )
                di.run()

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

            # Calculate program statistics
            console.print("  Calculating program statistics...")
            PEProgramStats.model_rebuild(_types_namespace={"Simulation": PESimulation})

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

            # Mark simulations and report as completed
            baseline_sim.status = SimulationStatus.COMPLETED
            baseline_sim.completed_at = datetime.now(timezone.utc)
            reform_sim.status = SimulationStatus.COMPLETED
            reform_sim.completed_at = datetime.now(timezone.utc)
            report.status = ReportStatus.COMPLETED

            session.add(baseline_sim)
            session.add(reform_sim)
            session.add(report)
            session.commit()

        console.print(f"[bold green]US report {report_id} completed[/bold green]")

    except Exception as e:
        console.print(f"[bold red]US report {report_id} failed: {e}[/bold red]")
        with Session(engine) as session:
            report = session.get(Report, UUID(report_id))
            if report:
                report.status = ReportStatus.FAILED
                report.error_message = str(e)
                session.add(report)
                session.commit()
        raise


def _get_pe_policy_uk(policy_id, model_version, session):
    """Convert database Policy to policyengine Policy for UK."""
    if policy_id is None:
        return None

    from policyengine.core.policy import ParameterValue as PEParameterValue
    from policyengine.core.policy import Policy as PEPolicy

    from policyengine_api.models import Policy

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


def _get_pe_policy_us(policy_id, model_version, session):
    """Convert database Policy to policyengine Policy for US."""
    # Same implementation as UK
    return _get_pe_policy_uk(policy_id, model_version, session)


def _get_pe_dynamic_uk(dynamic_id, model_version, session):
    """Convert database Dynamic to policyengine Dynamic for UK."""
    if dynamic_id is None:
        return None

    from policyengine.core.dynamic import Dynamic as PEDynamic
    from policyengine.core.policy import ParameterValue as PEParameterValue

    from policyengine_api.models import Dynamic

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


def _get_pe_dynamic_us(dynamic_id, model_version, session):
    """Convert database Dynamic to policyengine Dynamic for US."""
    # Same implementation as UK
    return _get_pe_dynamic_uk(dynamic_id, model_version, session)
