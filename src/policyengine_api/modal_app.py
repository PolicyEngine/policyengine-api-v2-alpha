"""Modal.com serverless functions for PolicyEngine compute.

This module defines Modal functions for running simulations and analyses
with sub-1s cold starts via memory snapshot restore. The heavy policyengine
imports happen at image build time, not runtime.

Function naming follows the API hierarchy:
- simulate_household_*: Single household calculation (/simulate/household)
- simulate_economy_*: Single economy simulation (/simulate/economy)
- economy_comparison_*: Full economy comparison analysis (/analysis/compare/economy)

Deploy with: modal deploy src/policyengine_api/modal_app.py
"""

import modal

# Base image with common dependencies using uv for fast installs
# Cache bust: 2026-01-11-v6-use-pe-aggregate
base_image = (
    modal.Image.debian_slim(python_version="3.13")
    .apt_install("libhdf5-dev")
    .pip_install("uv")
    .run_commands(
        "uv pip install --system --upgrade "
        "policyengine>=3.1.15 "
        "sqlmodel>=0.0.22 "
        "psycopg2-binary>=2.9.10 "
        "supabase>=2.10.0 "
        "rich>=13.9.4 "
        "logfire[httpx]>=3.0.0 "
        "tables>=3.10.0"  # pytables - required for HDF5 dataset operations
    )
    # Include the policyengine_api models package (copy=True allows subsequent build steps)
    .add_local_python_source("policyengine_api", copy=True)
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
uk_image = base_image.run_commands(
    "uv pip install --system policyengine-uk>=2.0.0"
).run_function(_import_uk)

# US image - uses run_function to snapshot imported modules in memory
us_image = base_image.run_commands(
    "uv pip install --system policyengine-us>=1.0.0"
).run_function(_import_us)

app = modal.App("policyengine")


# Secrets for database and observability
db_secrets = modal.Secret.from_name("policyengine-db")
logfire_secrets = modal.Secret.from_name("policyengine-logfire")

# Required environment variables from each secret
REQUIRED_DB_VARS = ["DATABASE_URL", "SUPABASE_URL", "SUPABASE_KEY"]
REQUIRED_LOGFIRE_VARS = ["LOGFIRE_TOKEN"]


@app.function(
    image=base_image,
    secrets=[db_secrets, logfire_secrets],
    timeout=30,
)
def validate_secrets() -> dict:
    """Validate all required secrets are configured correctly.

    Call this after deploy to verify secrets before running real workloads.
    Returns a dict with status and any missing variables.
    """
    import os

    missing = []
    present = []

    for var in REQUIRED_DB_VARS:
        if os.environ.get(var):
            present.append(var)
        else:
            missing.append(f"{var} (from policyengine-db)")

    for var in REQUIRED_LOGFIRE_VARS:
        if os.environ.get(var):
            present.append(var)
        else:
            missing.append(f"{var} (from policyengine-logfire)")

    if missing:
        return {
            "status": "error",
            "message": f"Missing environment variables: {', '.join(missing)}",
            "missing": missing,
            "present": present,
            "hint": (
                "Modal secrets must explicitly set env var names. "
                "Example: modal secret create policyengine-db "
                "DATABASE_URL=postgresql://... SUPABASE_URL=https://... SUPABASE_KEY=..."
            ),
        }

    return {
        "status": "ok",
        "message": "All required secrets are configured",
        "present": present,
    }


def configure_logfire(service_name: str, traceparent: str | None = None):
    """Configure logfire with optional trace context propagation.

    Args:
        service_name: Service name for spans (e.g. "policyengine-modal-uk")
        traceparent: W3C traceparent header for distributed tracing
    """
    import os

    import logfire

    token = os.environ.get("LOGFIRE_TOKEN", "")
    if not token:
        return

    logfire.configure(
        service_name=service_name,
        token=token,
        environment=os.environ.get("LOGFIRE_ENVIRONMENT", "production"),
        console=False,
    )

    # If traceparent provided, attach to the current context
    if traceparent:
        from opentelemetry import context
        from opentelemetry.trace.propagation.tracecontext import (
            TraceContextTextMapPropagator,
        )

        propagator = TraceContextTextMapPropagator()
        ctx = propagator.extract(carrier={"traceparent": traceparent})
        context.attach(ctx)


def get_database_url() -> str:
    """Get and validate database URL from environment."""
    import os

    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise ValueError(
            "DATABASE_URL environment variable is not set. "
            "The Modal secret 'policyengine-db' must include DATABASE_URL=postgresql://... "
            "Run: modal run policyengine::validate_secrets to debug."
        )
    if not url.startswith(("postgresql://", "postgres://")):
        raise ValueError(
            f"DATABASE_URL must start with postgresql:// or postgres://, got: {url[:50]}..."
        )
    return url


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


@app.function(
    image=uk_image,
    secrets=[db_secrets, logfire_secrets],
    memory=4096,
    cpu=4,
    timeout=600,
)
def simulate_household_uk(
    job_id: str,
    people: list[dict],
    benunit: dict,
    household: dict,
    year: int,
    policy_data: dict | None,
    dynamic_data: dict | None,
    traceparent: str | None = None,
) -> None:
    """Calculate UK household and write result to database."""
    import json
    from datetime import datetime, timezone

    import logfire
    from sqlmodel import Session, create_engine

    configure_logfire("policyengine-modal-uk", traceparent)

    try:
        with logfire.span("simulate_household_uk", job_id=job_id):
            database_url = get_database_url()
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

                with logfire.span("calculate_household_impact"):
                    result = calculate_household_impact(pe_input, policy=policy)

                # Write result to database
                with Session(engine) as session:
                    from sqlmodel import text

                    session.exec(
                        text("""
                            UPDATE household_jobs
                            SET status = 'COMPLETED',
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

            except Exception as e:
                logfire.error("UK household job failed", job_id=job_id, error=str(e))
                with Session(engine) as session:
                    from sqlmodel import text

                    session.exec(
                        text("""
                            UPDATE household_jobs
                            SET status = 'FAILED',
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
    finally:
        logfire.force_flush()


@app.function(
    image=us_image,
    secrets=[db_secrets, logfire_secrets],
    memory=4096,
    cpu=4,
    timeout=600,
)
def simulate_household_us(
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
    traceparent: str | None = None,
) -> None:
    """Calculate US household and write result to database."""
    import json
    from datetime import datetime, timezone

    import logfire
    from sqlmodel import Session, create_engine

    configure_logfire("policyengine-modal-us", traceparent)

    try:
        with logfire.span("simulate_household_us", job_id=job_id):
            database_url = get_database_url()
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

                with logfire.span("calculate_household_impact"):
                    result = calculate_household_impact(pe_input, policy=policy)

                # Write result to database
                with Session(engine) as session:
                    from sqlmodel import text

                    session.exec(
                        text("""
                            UPDATE household_jobs
                            SET status = 'COMPLETED',
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

            except Exception as e:
                logfire.error("US household job failed", job_id=job_id, error=str(e))
                with Session(engine) as session:
                    from sqlmodel import text

                    session.exec(
                        text("""
                            UPDATE household_jobs
                            SET status = 'FAILED',
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
    finally:
        logfire.force_flush()


@app.function(
    image=uk_image,
    secrets=[db_secrets, logfire_secrets],
    memory=8192,
    cpu=8,
    timeout=1800,
)
def simulate_economy_uk(simulation_id: str, traceparent: str | None = None) -> None:
    """Run a single UK economy simulation and write results to database."""
    import os
    from datetime import datetime, timezone
    from uuid import UUID

    import logfire
    from sqlmodel import Session, create_engine

    configure_logfire("policyengine-modal-uk", traceparent)

    try:
        with logfire.span("simulate_economy_uk", simulation_id=simulation_id):
            database_url = get_database_url()
            supabase_url = os.environ["SUPABASE_URL"]
            supabase_key = os.environ["SUPABASE_KEY"]
            storage_bucket = os.environ.get("STORAGE_BUCKET", "datasets")

            engine = create_engine(database_url)

            try:
                from policyengine_api.models import (
                    Dataset,
                    Simulation,
                    SimulationStatus,
                )

                with Session(engine) as session:
                    simulation = session.get(Simulation, UUID(simulation_id))
                    if not simulation:
                        raise ValueError(f"Simulation {simulation_id} not found")

                    # Skip if already completed
                    if simulation.status == SimulationStatus.COMPLETED:
                        logfire.info(
                            "Simulation already completed", simulation_id=simulation_id
                        )
                        return

                    # Update status to running
                    simulation.status = SimulationStatus.RUNNING
                    session.add(simulation)
                    session.commit()

                    # Get dataset
                    dataset = session.get(Dataset, simulation.dataset_id)
                    if not dataset:
                        raise ValueError(f"Dataset {simulation.dataset_id} not found")

                    # Import policyengine
                    from policyengine.core import Simulation as PESimulation
                    from policyengine.tax_benefit_models.uk import uk_latest
                    from policyengine.tax_benefit_models.uk.datasets import (
                        PolicyEngineUKDataset,
                    )

                    pe_model_version = uk_latest

                    # Get policy and dynamic
                    policy = _get_pe_policy_uk(
                        simulation.policy_id, pe_model_version, session
                    )
                    dynamic = _get_pe_dynamic_uk(
                        simulation.dynamic_id, pe_model_version, session
                    )

                    # Download dataset
                    local_path = download_dataset(
                        dataset.filepath, supabase_url, supabase_key, storage_bucket
                    )

                    pe_dataset = PolicyEngineUKDataset(
                        name=dataset.name,
                        description=dataset.description or "",
                        filepath=local_path,
                        year=dataset.year,
                    )

                    # Create and run simulation
                    with logfire.span("run_simulation"):
                        pe_sim = PESimulation(
                            dataset=pe_dataset,
                            tax_benefit_model_version=pe_model_version,
                            policy=policy,
                            dynamic=dynamic,
                        )
                        pe_sim.ensure()

                    # Save output dataset
                    with logfire.span("save_output_dataset"):
                        import tempfile
                        from supabase import create_client

                        output_filename = f"output_{simulation_id}.h5"
                        output_path = f"/tmp/{output_filename}"

                        # Set filepath and save
                        pe_sim.output_dataset.filepath = output_path
                        pe_sim.output_dataset.save()

                        # Upload to Supabase storage
                        supabase = create_client(supabase_url, supabase_key)
                        with open(output_path, "rb") as f:
                            supabase.storage.from_(storage_bucket).upload(
                                output_filename,
                                f,
                                {
                                    "content-type": "application/octet-stream",
                                    "upsert": "true",
                                },
                            )

                        # Create output dataset record
                        output_dataset = Dataset(
                            name=f"Output: {dataset.name}",
                            description=f"Output from simulation {simulation_id}",
                            filepath=output_filename,
                            year=dataset.year,
                            is_output_dataset=True,
                            tax_benefit_model_id=dataset.tax_benefit_model_id,
                        )
                        session.add(output_dataset)
                        session.commit()
                        session.refresh(output_dataset)

                        # Link to simulation
                        simulation.output_dataset_id = output_dataset.id

                    # Mark as completed
                    simulation.status = SimulationStatus.COMPLETED
                    simulation.completed_at = datetime.now(timezone.utc)
                    session.add(simulation)
                    session.commit()

            except Exception as e:
                logfire.error(
                    "UK economy simulation failed",
                    simulation_id=simulation_id,
                    error=str(e),
                )
                # Use raw SQL to mark as failed - models may not be available
                try:
                    from sqlmodel import text

                    with Session(engine) as session:
                        session.execute(
                            text(
                                "UPDATE simulations SET status = 'FAILED', error_message = :error "
                                "WHERE id = :sim_id"
                            ),
                            {"sim_id": simulation_id, "error": str(e)[:1000]},
                        )
                        session.commit()
                except Exception as db_error:
                    logfire.error("Failed to update DB", error=str(db_error))
                raise
    finally:
        logfire.force_flush()


@app.function(
    image=us_image,
    secrets=[db_secrets, logfire_secrets],
    memory=8192,
    cpu=8,
    timeout=1800,
)
def simulate_economy_us(simulation_id: str, traceparent: str | None = None) -> None:
    """Run a single US economy simulation and write results to database."""
    import os
    from datetime import datetime, timezone
    from uuid import UUID

    import logfire
    from sqlmodel import Session, create_engine

    configure_logfire("policyengine-modal-us", traceparent)

    try:
        with logfire.span("simulate_economy_us", simulation_id=simulation_id):
            database_url = get_database_url()
            supabase_url = os.environ["SUPABASE_URL"]
            supabase_key = os.environ["SUPABASE_KEY"]
            storage_bucket = os.environ.get("STORAGE_BUCKET", "datasets")

            engine = create_engine(database_url)

            try:
                from policyengine_api.models import (
                    Dataset,
                    Simulation,
                    SimulationStatus,
                )

                with Session(engine) as session:
                    simulation = session.get(Simulation, UUID(simulation_id))
                    if not simulation:
                        raise ValueError(f"Simulation {simulation_id} not found")

                    # Skip if already completed
                    if simulation.status == SimulationStatus.COMPLETED:
                        logfire.info(
                            "Simulation already completed", simulation_id=simulation_id
                        )
                        return

                    # Update status to running
                    simulation.status = SimulationStatus.RUNNING
                    session.add(simulation)
                    session.commit()

                    # Get dataset
                    dataset = session.get(Dataset, simulation.dataset_id)
                    if not dataset:
                        raise ValueError(f"Dataset {simulation.dataset_id} not found")

                    # Import policyengine
                    from policyengine.core import Simulation as PESimulation
                    from policyengine.tax_benefit_models.us import us_latest
                    from policyengine.tax_benefit_models.us.datasets import (
                        PolicyEngineUSDataset,
                    )

                    pe_model_version = us_latest

                    # Get policy and dynamic
                    policy = _get_pe_policy_us(
                        simulation.policy_id, pe_model_version, session
                    )
                    dynamic = _get_pe_dynamic_us(
                        simulation.dynamic_id, pe_model_version, session
                    )

                    # Download dataset
                    local_path = download_dataset(
                        dataset.filepath, supabase_url, supabase_key, storage_bucket
                    )

                    pe_dataset = PolicyEngineUSDataset(
                        name=dataset.name,
                        description=dataset.description or "",
                        filepath=local_path,
                        year=dataset.year,
                    )

                    # Create and run simulation
                    with logfire.span("run_simulation"):
                        pe_sim = PESimulation(
                            dataset=pe_dataset,
                            tax_benefit_model_version=pe_model_version,
                            policy=policy,
                            dynamic=dynamic,
                        )
                        pe_sim.ensure()

                    # Save output dataset
                    with logfire.span("save_output_dataset"):
                        from supabase import create_client

                        output_filename = f"output_{simulation_id}.h5"
                        output_path = f"/tmp/{output_filename}"

                        # Set filepath and save
                        pe_sim.output_dataset.filepath = output_path
                        pe_sim.output_dataset.save()

                        # Upload to Supabase storage
                        supabase = create_client(supabase_url, supabase_key)
                        with open(output_path, "rb") as f:
                            supabase.storage.from_(storage_bucket).upload(
                                output_filename,
                                f,
                                {
                                    "content-type": "application/octet-stream",
                                    "upsert": "true",
                                },
                            )

                        # Create output dataset record
                        output_dataset = Dataset(
                            name=f"Output: {dataset.name}",
                            description=f"Output from simulation {simulation_id}",
                            filepath=output_filename,
                            year=dataset.year,
                            is_output_dataset=True,
                            tax_benefit_model_id=dataset.tax_benefit_model_id,
                        )
                        session.add(output_dataset)
                        session.commit()
                        session.refresh(output_dataset)

                        # Link to simulation
                        simulation.output_dataset_id = output_dataset.id

                    # Mark as completed
                    simulation.status = SimulationStatus.COMPLETED
                    simulation.completed_at = datetime.now(timezone.utc)
                    session.add(simulation)
                    session.commit()

            except Exception as e:
                logfire.error(
                    "US economy simulation failed",
                    simulation_id=simulation_id,
                    error=str(e),
                )
                # Use raw SQL to mark as failed - models may not be available
                try:
                    from sqlmodel import text

                    with Session(engine) as session:
                        session.execute(
                            text(
                                "UPDATE simulations SET status = 'FAILED', error_message = :error "
                                "WHERE id = :sim_id"
                            ),
                            {"sim_id": simulation_id, "error": str(e)[:1000]},
                        )
                    session.commit()
                except Exception as db_error:
                    logfire.error("Failed to update DB", error=str(db_error))
                raise
    finally:
        logfire.force_flush()


@app.function(
    image=uk_image,
    secrets=[db_secrets, logfire_secrets],
    memory=8192,
    cpu=8,
    timeout=1800,
)
def economy_comparison_uk(job_id: str, traceparent: str | None = None) -> None:
    """Run UK economy comparison analysis (decile impacts, budget impact, etc)."""
    import os

    import logfire

    # Configure logfire FIRST to capture all time including imports
    configure_logfire("policyengine-modal-uk", traceparent)

    try:
        with logfire.span("economy_comparison_uk", job_id=job_id):
            from datetime import datetime, timezone
            from uuid import UUID

            from sqlmodel import Session, create_engine

            database_url = get_database_url()
            supabase_url = os.environ["SUPABASE_URL"]
            supabase_key = os.environ["SUPABASE_KEY"]
            storage_bucket = os.environ.get("STORAGE_BUCKET", "datasets")

            # Debug: log the key role
            import base64
            import json
            try:
                payload = supabase_key.split('.')[1]
                payload += '=' * (4 - len(payload) % 4)
                decoded = json.loads(base64.urlsafe_b64decode(payload))
                logfire.info("Supabase key info", role=decoded.get('role', 'unknown'))
            except Exception as e:
                logfire.warn("Could not decode key", error=str(e))

            engine = create_engine(database_url)

            try:
                # Import models inline
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

                with Session(engine) as session:
                    # Load report and related data
                    report = session.get(Report, UUID(job_id))
                    if not report:
                        raise ValueError(f"Report {job_id} not found")

                    baseline_sim = session.get(
                        Simulation, report.baseline_simulation_id
                    )
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
                        TaxBenefitModelVersion,
                        baseline_sim.tax_benefit_model_version_id,
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
                    with logfire.span("download_dataset", filepath=dataset.filepath):
                        local_path = download_dataset(
                            dataset.filepath, supabase_url, supabase_key, storage_bucket
                        )

                    with logfire.span("load_dataset"):
                        pe_dataset = PolicyEngineUKDataset(
                            name=dataset.name,
                            description=dataset.description or "",
                            filepath=local_path,
                            year=dataset.year,
                        )

                    # Create and run simulations
                    with logfire.span("run_baseline_simulation"):
                        pe_baseline_sim = PESimulation(
                            dataset=pe_dataset,
                            tax_benefit_model_version=pe_model_version,
                            policy=baseline_policy,
                            dynamic=baseline_dynamic,
                        )
                        pe_baseline_sim.ensure()

                    with logfire.span("run_reform_simulation"):
                        pe_reform_sim = PESimulation(
                            dataset=pe_dataset,
                            tax_benefit_model_version=pe_model_version,
                            policy=reform_policy,
                            dynamic=reform_dynamic,
                        )
                        pe_reform_sim.ensure()

                    # Pre-calculate key UK variables to include in output
                    # (PolicyEngine is lazy - variables only calculated when accessed)
                    uk_key_variables = [
                        "hbai_household_net_income",
                        "household_net_income",
                        "equiv_household_net_income",
                        "income_tax",
                        "national_insurance",
                        "universal_credit",
                        "child_benefit",
                        "pension_credit",
                        "housing_benefit",
                        "council_tax",
                        "household_benefits",
                        "household_tax",
                    ]
                    with logfire.span("precalculate_variables"):
                        for var in uk_key_variables:
                            try:
                                pe_baseline_sim[var]
                                pe_reform_sim[var]
                            except Exception:
                                pass  # Variable may not exist in model

                    # Save output datasets for both simulations
                    from supabase import create_client

                    supabase = create_client(supabase_url, supabase_key)

                    # Save baseline output
                    with logfire.span("save_baseline_output"):
                        baseline_output_filename = f"output_{baseline_sim.id}.h5"
                        baseline_output_path = f"/tmp/{baseline_output_filename}"
                        pe_baseline_sim.output_dataset.filepath = baseline_output_path
                        pe_baseline_sim.output_dataset.save()

                        with open(baseline_output_path, "rb") as f:
                            supabase.storage.from_(storage_bucket).upload(
                                baseline_output_filename,
                                f,
                                {
                                    "content-type": "application/octet-stream",
                                    "upsert": "true",
                                },
                            )

                        baseline_output_dataset = Dataset(
                            name=f"Output: {dataset.name} (baseline)",
                            description=f"Output from baseline simulation {baseline_sim.id}",
                            filepath=baseline_output_filename,
                            year=dataset.year,
                            is_output_dataset=True,
                            tax_benefit_model_id=dataset.tax_benefit_model_id,
                        )
                        session.add(baseline_output_dataset)
                        session.commit()
                        session.refresh(baseline_output_dataset)
                        baseline_sim.output_dataset_id = baseline_output_dataset.id

                    # Save reform output
                    with logfire.span("save_reform_output"):
                        reform_output_filename = f"output_{reform_sim.id}.h5"
                        reform_output_path = f"/tmp/{reform_output_filename}"
                        pe_reform_sim.output_dataset.filepath = reform_output_path
                        pe_reform_sim.output_dataset.save()

                        with open(reform_output_path, "rb") as f:
                            supabase.storage.from_(storage_bucket).upload(
                                reform_output_filename,
                                f,
                                {
                                    "content-type": "application/octet-stream",
                                    "upsert": "true",
                                },
                            )

                        reform_output_dataset = Dataset(
                            name=f"Output: {dataset.name} (reform)",
                            description=f"Output from reform simulation {reform_sim.id}",
                            filepath=reform_output_filename,
                            year=dataset.year,
                            is_output_dataset=True,
                            tax_benefit_model_id=dataset.tax_benefit_model_id,
                        )
                        session.add(reform_output_dataset)
                        session.commit()
                        session.refresh(reform_output_dataset)
                        reform_sim.output_dataset_id = reform_output_dataset.id

                    # Calculate decile impacts
                    with logfire.span("calculate_decile_impacts"):
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
                    with logfire.span("calculate_program_statistics"):
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
                            except KeyError:
                                pass  # Variable not in model, skip silently

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

            except Exception as e:
                logfire.error(
                    "UK economy comparison failed", job_id=job_id, error=str(e)
                )
                # Use raw SQL to mark as failed - models may not be available
                try:
                    from sqlmodel import text

                    with Session(engine) as session:
                        session.execute(
                            text(
                                "UPDATE reports SET status = 'FAILED', error_message = :error "
                                "WHERE id = :job_id"
                            ),
                            {"job_id": job_id, "error": str(e)[:1000]},
                        )
                        session.commit()
                except Exception as db_error:
                    logfire.error("Failed to update DB", error=str(db_error))
                raise
    finally:
        logfire.force_flush()


@app.function(
    image=us_image,
    secrets=[db_secrets, logfire_secrets],
    memory=8192,
    cpu=8,
    timeout=1800,
)
def economy_comparison_us(job_id: str, traceparent: str | None = None) -> None:
    """Run US economy comparison analysis (decile impacts, budget impact, etc)."""
    import os
    from datetime import datetime, timezone
    from uuid import UUID

    import logfire
    from sqlmodel import Session, create_engine

    configure_logfire("policyengine-modal-us", traceparent)

    try:
        with logfire.span("economy_comparison_us", job_id=job_id):
            database_url = get_database_url()
            supabase_url = os.environ["SUPABASE_URL"]
            supabase_key = os.environ["SUPABASE_KEY"]
            storage_bucket = os.environ.get("STORAGE_BUCKET", "datasets")

            engine = create_engine(database_url)

            try:
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

                with Session(engine) as session:
                    # Load report and related data
                    report = session.get(Report, UUID(job_id))
                    if not report:
                        raise ValueError(f"Report {job_id} not found")

                    baseline_sim = session.get(
                        Simulation, report.baseline_simulation_id
                    )
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
                    with logfire.span("run_baseline_simulation"):
                        pe_baseline_sim = PESimulation(
                            dataset=pe_dataset,
                            tax_benefit_model_version=pe_model_version,
                            policy=baseline_policy,
                            dynamic=baseline_dynamic,
                        )
                        pe_baseline_sim.ensure()

                    with logfire.span("run_reform_simulation"):
                        pe_reform_sim = PESimulation(
                            dataset=pe_dataset,
                            tax_benefit_model_version=pe_model_version,
                            policy=reform_policy,
                            dynamic=reform_dynamic,
                        )
                        pe_reform_sim.ensure()

                    # Save output datasets for both simulations
                    from supabase import create_client

                    supabase = create_client(supabase_url, supabase_key)

                    # Save baseline output
                    with logfire.span("save_baseline_output"):
                        baseline_output_filename = f"output_{baseline_sim.id}.h5"
                        baseline_output_path = f"/tmp/{baseline_output_filename}"
                        pe_baseline_sim.output_dataset.filepath = baseline_output_path
                        pe_baseline_sim.output_dataset.save()

                        with open(baseline_output_path, "rb") as f:
                            supabase.storage.from_(storage_bucket).upload(
                                baseline_output_filename,
                                f,
                                {
                                    "content-type": "application/octet-stream",
                                    "upsert": "true",
                                },
                            )

                        baseline_output_dataset = Dataset(
                            name=f"Output: {dataset.name} (baseline)",
                            description=f"Output from baseline simulation {baseline_sim.id}",
                            filepath=baseline_output_filename,
                            year=dataset.year,
                            is_output_dataset=True,
                            tax_benefit_model_id=dataset.tax_benefit_model_id,
                        )
                        session.add(baseline_output_dataset)
                        session.commit()
                        session.refresh(baseline_output_dataset)
                        baseline_sim.output_dataset_id = baseline_output_dataset.id

                    # Save reform output
                    with logfire.span("save_reform_output"):
                        reform_output_filename = f"output_{reform_sim.id}.h5"
                        reform_output_path = f"/tmp/{reform_output_filename}"
                        pe_reform_sim.output_dataset.filepath = reform_output_path
                        pe_reform_sim.output_dataset.save()

                        with open(reform_output_path, "rb") as f:
                            supabase.storage.from_(storage_bucket).upload(
                                reform_output_filename,
                                f,
                                {
                                    "content-type": "application/octet-stream",
                                    "upsert": "true",
                                },
                            )

                        reform_output_dataset = Dataset(
                            name=f"Output: {dataset.name} (reform)",
                            description=f"Output from reform simulation {reform_sim.id}",
                            filepath=reform_output_filename,
                            year=dataset.year,
                            is_output_dataset=True,
                            tax_benefit_model_id=dataset.tax_benefit_model_id,
                        )
                        session.add(reform_output_dataset)
                        session.commit()
                        session.refresh(reform_output_dataset)
                        reform_sim.output_dataset_id = reform_output_dataset.id

                    # Calculate decile impacts
                    with logfire.span("calculate_decile_impacts"):
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
                    with logfire.span("calculate_program_statistics"):
                        PEProgramStats.model_rebuild(
                            _types_namespace={"Simulation": PESimulation}
                        )

                        programs = {
                            "income_tax": {"entity": "tax_unit", "is_tax": True},
                            "employee_payroll_tax": {
                                "entity": "person",
                                "is_tax": True,
                            },
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
                            except KeyError:
                                pass  # Variable not in model, skip silently

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

            except Exception as e:
                logfire.error(
                    "US economy comparison failed", job_id=job_id, error=str(e)
                )
                # Use raw SQL to mark as failed - models may not be available
                try:
                    from sqlmodel import text

                    with Session(engine) as session:
                        session.execute(
                            text(
                                "UPDATE reports SET status = 'FAILED', error_message = :error "
                                "WHERE id = :job_id"
                            ),
                            {"job_id": job_id, "error": str(e)[:1000]},
                        )
                        session.commit()
                except Exception as db_error:
                    logfire.error("Failed to update DB", error=str(db_error))
                raise
    finally:
        logfire.force_flush()


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


@app.function(
    image=uk_image,
    secrets=[db_secrets, logfire_secrets],
    memory=8192,
    cpu=8,
    timeout=1800,
)
def compute_aggregate_uk(aggregate_id: str, traceparent: str | None = None) -> None:
    """Compute a UK aggregate output and write result to database."""
    import os
    from uuid import UUID

    import logfire
    from sqlmodel import Session, create_engine

    configure_logfire("policyengine-modal-uk", traceparent)

    try:
        with logfire.span("compute_aggregate_uk", aggregate_id=aggregate_id):
            database_url = get_database_url()
            supabase_url = os.environ["SUPABASE_URL"]
            supabase_key = os.environ["SUPABASE_KEY"]
            storage_bucket = os.environ.get("STORAGE_BUCKET", "datasets")

            engine = create_engine(database_url)

            try:
                from policyengine.core import Simulation as PESimulation
                from policyengine.outputs import Aggregate as PEAggregate
                from policyengine.outputs import AggregateType as PEAggregateType
                from policyengine.tax_benefit_models.uk import uk_latest
                from policyengine.tax_benefit_models.uk.datasets import (
                    PolicyEngineUKDataset,
                )

                from policyengine_api.models import (
                    AggregateOutput,
                    AggregateStatus,
                    Dataset,
                    Simulation,
                )

                with Session(engine) as session:
                    aggregate = session.get(AggregateOutput, UUID(aggregate_id))
                    if not aggregate:
                        raise ValueError(f"Aggregate {aggregate_id} not found")

                    # Skip if already completed
                    if aggregate.status == AggregateStatus.COMPLETED:
                        logfire.info(
                            "Aggregate already completed", aggregate_id=aggregate_id
                        )
                        return

                    # Update status to running
                    aggregate.status = AggregateStatus.RUNNING
                    session.add(aggregate)
                    session.commit()

                    # Get simulation
                    simulation = session.get(Simulation, aggregate.simulation_id)
                    if not simulation:
                        raise ValueError(
                            f"Simulation {aggregate.simulation_id} not found"
                        )

                    # Check if simulation has stored output
                    if not simulation.output_dataset_id:
                        raise ValueError(
                            f"Simulation {aggregate.simulation_id} has no stored output. "
                            "Re-run the simulation to generate output."
                        )

                    output_dataset = session.get(Dataset, simulation.output_dataset_id)
                    if not output_dataset:
                        raise ValueError(
                            f"Output dataset {simulation.output_dataset_id} not found"
                        )

                    # Download output dataset
                    with logfire.span(
                        "download_output", filepath=output_dataset.filepath
                    ):
                        local_path = download_dataset(
                            output_dataset.filepath,
                            supabase_url,
                            supabase_key,
                            storage_bucket,
                        )

                    # Create policyengine simulation with loaded output
                    with logfire.span("load_output"):
                        pe_output_dataset = PolicyEngineUKDataset(
                            name=output_dataset.name or "output",
                            description=output_dataset.description or "",
                            filepath=local_path,
                            year=output_dataset.year,
                            is_output_dataset=True,
                        )

                        pe_sim = PESimulation(
                            dataset=pe_output_dataset,  # Use output as dataset
                            tax_benefit_model_version=uk_latest,
                        )
                        pe_sim.output_dataset = pe_output_dataset

                    # Calculate aggregate using policyengine
                    with logfire.span(
                        "calculate_aggregate",
                        variable=aggregate.variable,
                        aggregate_type=str(aggregate.aggregate_type),
                    ):
                        pe_aggregate = PEAggregate(
                            simulation=pe_sim,
                            variable=aggregate.variable,
                            aggregate_type=PEAggregateType(aggregate.aggregate_type.value),
                            entity=aggregate.entity,
                        )
                        pe_aggregate.run()
                        result = float(pe_aggregate.result)

                    # Update aggregate with result
                    aggregate.result = result
                    aggregate.status = AggregateStatus.COMPLETED
                    session.add(aggregate)
                    session.commit()

            except Exception as e:
                logfire.error(
                    "UK aggregate computation failed",
                    aggregate_id=aggregate_id,
                    error=str(e),
                )
                try:
                    from sqlmodel import text

                    with Session(engine) as session:
                        session.execute(
                            text(
                                "UPDATE aggregates SET status = 'FAILED', error_message = :error "
                                "WHERE id = :agg_id"
                            ),
                            {"agg_id": aggregate_id, "error": str(e)[:1000]},
                        )
                        session.commit()
                except Exception as db_error:
                    logfire.error("Failed to update DB", error=str(db_error))
                raise
    finally:
        logfire.force_flush()


@app.function(
    image=us_image,
    secrets=[db_secrets, logfire_secrets],
    memory=8192,
    cpu=8,
    timeout=1800,
)
def compute_aggregate_us(aggregate_id: str, traceparent: str | None = None) -> None:
    """Compute a US aggregate output and write result to database."""
    import os
    from uuid import UUID

    import logfire
    from sqlmodel import Session, create_engine

    configure_logfire("policyengine-modal-us", traceparent)

    try:
        with logfire.span("compute_aggregate_us", aggregate_id=aggregate_id):
            database_url = get_database_url()
            supabase_url = os.environ["SUPABASE_URL"]
            supabase_key = os.environ["SUPABASE_KEY"]
            storage_bucket = os.environ.get("STORAGE_BUCKET", "datasets")

            engine = create_engine(database_url)

            try:
                from policyengine.core import Simulation as PESimulation
                from policyengine.outputs import Aggregate as PEAggregate
                from policyengine.outputs import AggregateType as PEAggregateType
                from policyengine.tax_benefit_models.us import us_latest
                from policyengine.tax_benefit_models.us.datasets import (
                    PolicyEngineUSDataset,
                )

                from policyengine_api.models import (
                    AggregateOutput,
                    AggregateStatus,
                    Dataset,
                    Simulation,
                )

                with Session(engine) as session:
                    aggregate = session.get(AggregateOutput, UUID(aggregate_id))
                    if not aggregate:
                        raise ValueError(f"Aggregate {aggregate_id} not found")

                    if aggregate.status == AggregateStatus.COMPLETED:
                        logfire.info(
                            "Aggregate already completed", aggregate_id=aggregate_id
                        )
                        return

                    aggregate.status = AggregateStatus.RUNNING
                    session.add(aggregate)
                    session.commit()

                    simulation = session.get(Simulation, aggregate.simulation_id)
                    if not simulation:
                        raise ValueError(
                            f"Simulation {aggregate.simulation_id} not found"
                        )

                    if not simulation.output_dataset_id:
                        raise ValueError(
                            f"Simulation {aggregate.simulation_id} has no stored output."
                        )

                    output_dataset = session.get(Dataset, simulation.output_dataset_id)
                    if not output_dataset:
                        raise ValueError(
                            f"Output dataset {simulation.output_dataset_id} not found"
                        )

                    with logfire.span(
                        "download_output", filepath=output_dataset.filepath
                    ):
                        local_path = download_dataset(
                            output_dataset.filepath,
                            supabase_url,
                            supabase_key,
                            storage_bucket,
                        )

                    with logfire.span("load_output"):
                        pe_output_dataset = PolicyEngineUSDataset(
                            name=output_dataset.name or "output",
                            description=output_dataset.description or "",
                            filepath=local_path,
                            year=output_dataset.year,
                            is_output_dataset=True,
                        )

                        pe_sim = PESimulation(
                            dataset=pe_output_dataset,
                            tax_benefit_model_version=us_latest,
                        )
                        pe_sim.output_dataset = pe_output_dataset

                    with logfire.span(
                        "calculate_aggregate",
                        variable=aggregate.variable,
                        aggregate_type=str(aggregate.aggregate_type),
                    ):
                        pe_aggregate = PEAggregate(
                            simulation=pe_sim,
                            variable=aggregate.variable,
                            aggregate_type=PEAggregateType(aggregate.aggregate_type.value),
                            entity=aggregate.entity,
                        )
                        pe_aggregate.run()
                        result = float(pe_aggregate.result)

                    aggregate.result = result
                    aggregate.status = AggregateStatus.COMPLETED
                    session.add(aggregate)
                    session.commit()

            except Exception as e:
                logfire.error(
                    "US aggregate computation failed",
                    aggregate_id=aggregate_id,
                    error=str(e),
                )
                try:
                    from sqlmodel import text

                    with Session(engine) as session:
                        session.execute(
                            text(
                                "UPDATE aggregates SET status = 'FAILED', error_message = :error "
                                "WHERE id = :agg_id"
                            ),
                            {"agg_id": aggregate_id, "error": str(e)[:1000]},
                        )
                        session.commit()
                except Exception as db_error:
                    logfire.error("Failed to update DB", error=str(db_error))
                raise
    finally:
        logfire.force_flush()


@app.function(
    image=uk_image,
    secrets=[db_secrets, logfire_secrets],
    memory=8192,
    cpu=8,
    timeout=1800,
)
def compute_change_aggregate_uk(
    change_aggregate_id: str, traceparent: str | None = None
) -> None:
    """Compute a UK change aggregate and write result to database."""
    import os
    from uuid import UUID

    import logfire
    from sqlmodel import Session, create_engine

    configure_logfire("policyengine-modal-uk", traceparent)

    try:
        with logfire.span(
            "compute_change_aggregate_uk", change_aggregate_id=change_aggregate_id
        ):
            database_url = get_database_url()
            supabase_url = os.environ["SUPABASE_URL"]
            supabase_key = os.environ["SUPABASE_KEY"]
            storage_bucket = os.environ.get("STORAGE_BUCKET", "datasets")

            engine = create_engine(database_url)

            try:
                from policyengine_api.models import (
                    ChangeAggregate,
                    ChangeAggregateStatus,
                    ChangeAggregateType,
                    Dataset,
                    Simulation,
                )

                with Session(engine) as session:
                    change_agg = session.get(ChangeAggregate, UUID(change_aggregate_id))
                    if not change_agg:
                        raise ValueError(
                            f"ChangeAggregate {change_aggregate_id} not found"
                        )

                    # Skip if already completed
                    if change_agg.status == ChangeAggregateStatus.COMPLETED:
                        logfire.info(
                            "Change aggregate already completed",
                            change_aggregate_id=change_aggregate_id,
                        )
                        return

                    # Update status to running
                    change_agg.status = ChangeAggregateStatus.RUNNING
                    session.add(change_agg)
                    session.commit()

                    # Get simulations
                    baseline_sim = session.get(
                        Simulation, change_agg.baseline_simulation_id
                    )
                    reform_sim = session.get(
                        Simulation, change_agg.reform_simulation_id
                    )

                    if not baseline_sim or not reform_sim:
                        raise ValueError("Simulations not found")

                    # Check both simulations have stored outputs
                    if not baseline_sim.output_dataset_id:
                        raise ValueError(
                            f"Baseline simulation {change_agg.baseline_simulation_id} "
                            "has no stored output."
                        )
                    if not reform_sim.output_dataset_id:
                        raise ValueError(
                            f"Reform simulation {change_agg.reform_simulation_id} "
                            "has no stored output."
                        )

                    baseline_output = session.get(
                        Dataset, baseline_sim.output_dataset_id
                    )
                    reform_output = session.get(Dataset, reform_sim.output_dataset_id)

                    if not baseline_output or not reform_output:
                        raise ValueError("Output datasets not found")

                    # Load output datasets
                    import pandas as pd

                    entity = change_agg.entity or "person"

                    with logfire.span("load_baseline_output"):
                        baseline_path = download_dataset(
                            baseline_output.filepath,
                            supabase_url,
                            supabase_key,
                            storage_bucket,
                        )
                        with pd.HDFStore(baseline_path, mode="r") as store:
                            baseline_df = store[entity]

                    with logfire.span("load_reform_output"):
                        reform_path = download_dataset(
                            reform_output.filepath,
                            supabase_url,
                            supabase_key,
                            storage_bucket,
                        )
                        with pd.HDFStore(reform_path, mode="r") as store:
                            reform_df = store[entity]

                    # Calculate change aggregate
                    with logfire.span(
                        "calculate_change_aggregate",
                        variable=change_agg.variable,
                        aggregate_type=change_agg.aggregate_type,
                    ):
                        baseline_values = baseline_df[change_agg.variable].values
                        reform_values = reform_df[change_agg.variable].values
                        change_values = reform_values - baseline_values

                        # Apply filter if configured
                        if change_agg.filter_config:
                            import numpy as np

                            mask = np.ones(len(change_values), dtype=bool)
                            for (
                                filter_var,
                                filter_val,
                            ) in change_agg.filter_config.items():
                                filter_values = baseline_df[filter_var].values
                                if isinstance(filter_val, dict):
                                    if "gte" in filter_val:
                                        mask &= filter_values >= filter_val["gte"]
                                    if "lte" in filter_val:
                                        mask &= filter_values <= filter_val["lte"]
                                    if "eq" in filter_val:
                                        mask &= filter_values == filter_val["eq"]
                                else:
                                    mask &= filter_values == filter_val
                            change_values = change_values[mask]

                        # Apply change_geq/change_leq filters
                        if change_agg.change_geq is not None:
                            change_values = change_values[
                                change_values >= change_agg.change_geq
                            ]
                        if change_agg.change_leq is not None:
                            change_values = change_values[
                                change_values <= change_agg.change_leq
                            ]

                        # Calculate aggregate
                        if change_agg.aggregate_type == ChangeAggregateType.SUM:
                            result = float(change_values.sum())
                        elif change_agg.aggregate_type == ChangeAggregateType.MEAN:
                            result = (
                                float(change_values.mean())
                                if len(change_values) > 0
                                else 0.0
                            )
                        elif change_agg.aggregate_type == ChangeAggregateType.COUNT:
                            result = float(len(change_values))
                        else:
                            raise ValueError(
                                f"Unknown aggregate type: {change_agg.aggregate_type}"
                            )

                    # Update change aggregate with result
                    change_agg.result = result
                    change_agg.status = ChangeAggregateStatus.COMPLETED
                    session.add(change_agg)
                    session.commit()

            except Exception as e:
                logfire.error(
                    "UK change aggregate computation failed",
                    change_aggregate_id=change_aggregate_id,
                    error=str(e),
                )
                try:
                    from sqlmodel import text

                    with Session(engine) as session:
                        session.execute(
                            text(
                                "UPDATE change_aggregates SET status = 'FAILED', error_message = :error "
                                "WHERE id = :agg_id"
                            ),
                            {"agg_id": change_aggregate_id, "error": str(e)[:1000]},
                        )
                        session.commit()
                except Exception as db_error:
                    logfire.error("Failed to update DB", error=str(db_error))
                raise
    finally:
        logfire.force_flush()


@app.function(
    image=us_image,
    secrets=[db_secrets, logfire_secrets],
    memory=8192,
    cpu=8,
    timeout=1800,
)
def compute_change_aggregate_us(
    change_aggregate_id: str, traceparent: str | None = None
) -> None:
    """Compute a US change aggregate and write result to database."""
    import os
    from uuid import UUID

    import logfire
    from sqlmodel import Session, create_engine

    configure_logfire("policyengine-modal-us", traceparent)

    try:
        with logfire.span(
            "compute_change_aggregate_us", change_aggregate_id=change_aggregate_id
        ):
            database_url = get_database_url()
            supabase_url = os.environ["SUPABASE_URL"]
            supabase_key = os.environ["SUPABASE_KEY"]
            storage_bucket = os.environ.get("STORAGE_BUCKET", "datasets")

            engine = create_engine(database_url)

            try:
                from policyengine_api.models import (
                    ChangeAggregate,
                    ChangeAggregateStatus,
                    ChangeAggregateType,
                    Dataset,
                    Simulation,
                )

                with Session(engine) as session:
                    change_agg = session.get(ChangeAggregate, UUID(change_aggregate_id))
                    if not change_agg:
                        raise ValueError(
                            f"ChangeAggregate {change_aggregate_id} not found"
                        )

                    # Skip if already completed
                    if change_agg.status == ChangeAggregateStatus.COMPLETED:
                        logfire.info(
                            "Change aggregate already completed",
                            change_aggregate_id=change_aggregate_id,
                        )
                        return

                    # Update status to running
                    change_agg.status = ChangeAggregateStatus.RUNNING
                    session.add(change_agg)
                    session.commit()

                    # Get simulations
                    baseline_sim = session.get(
                        Simulation, change_agg.baseline_simulation_id
                    )
                    reform_sim = session.get(
                        Simulation, change_agg.reform_simulation_id
                    )

                    if not baseline_sim or not reform_sim:
                        raise ValueError("Simulations not found")

                    # Check both simulations have stored outputs
                    if not baseline_sim.output_dataset_id:
                        raise ValueError(
                            f"Baseline simulation {change_agg.baseline_simulation_id} "
                            "has no stored output."
                        )
                    if not reform_sim.output_dataset_id:
                        raise ValueError(
                            f"Reform simulation {change_agg.reform_simulation_id} "
                            "has no stored output."
                        )

                    baseline_output = session.get(
                        Dataset, baseline_sim.output_dataset_id
                    )
                    reform_output = session.get(Dataset, reform_sim.output_dataset_id)

                    if not baseline_output or not reform_output:
                        raise ValueError("Output datasets not found")

                    # Load output datasets
                    import pandas as pd

                    entity = change_agg.entity or "person"

                    with logfire.span("load_baseline_output"):
                        baseline_path = download_dataset(
                            baseline_output.filepath,
                            supabase_url,
                            supabase_key,
                            storage_bucket,
                        )
                        with pd.HDFStore(baseline_path, mode="r") as store:
                            baseline_df = store[entity]

                    with logfire.span("load_reform_output"):
                        reform_path = download_dataset(
                            reform_output.filepath,
                            supabase_url,
                            supabase_key,
                            storage_bucket,
                        )
                        with pd.HDFStore(reform_path, mode="r") as store:
                            reform_df = store[entity]

                    # Calculate change aggregate
                    with logfire.span(
                        "calculate_change_aggregate",
                        variable=change_agg.variable,
                        aggregate_type=change_agg.aggregate_type,
                    ):
                        baseline_values = baseline_df[change_agg.variable].values
                        reform_values = reform_df[change_agg.variable].values

                        # Calculate change
                        change_values = reform_values - baseline_values

                        # Apply filter if configured
                        if change_agg.filter_config:
                            import numpy as np

                            mask = np.ones(len(change_values), dtype=bool)
                            for (
                                filter_var,
                                filter_val,
                            ) in change_agg.filter_config.items():
                                filter_values = baseline_df[filter_var].values
                                if isinstance(filter_val, dict):
                                    if "gte" in filter_val:
                                        mask &= filter_values >= filter_val["gte"]
                                    if "lte" in filter_val:
                                        mask &= filter_values <= filter_val["lte"]
                                    if "eq" in filter_val:
                                        mask &= filter_values == filter_val["eq"]
                                else:
                                    mask &= filter_values == filter_val
                            change_values = change_values[mask]

                        # Apply change_geq/change_leq filters
                        if change_agg.change_geq is not None:
                            change_values = change_values[
                                change_values >= change_agg.change_geq
                            ]
                        if change_agg.change_leq is not None:
                            change_values = change_values[
                                change_values <= change_agg.change_leq
                            ]

                        # Calculate aggregate
                        if change_agg.aggregate_type == ChangeAggregateType.SUM:
                            result = float(change_values.sum())
                        elif change_agg.aggregate_type == ChangeAggregateType.MEAN:
                            result = (
                                float(change_values.mean())
                                if len(change_values) > 0
                                else 0.0
                            )
                        elif change_agg.aggregate_type == ChangeAggregateType.COUNT:
                            result = float(len(change_values))
                        else:
                            raise ValueError(
                                f"Unknown aggregate type: {change_agg.aggregate_type}"
                            )

                    # Update change aggregate with result
                    change_agg.result = result
                    change_agg.status = ChangeAggregateStatus.COMPLETED
                    session.add(change_agg)
                    session.commit()

            except Exception as e:
                logfire.error(
                    "US change aggregate computation failed",
                    change_aggregate_id=change_aggregate_id,
                    error=str(e),
                )
                try:
                    from sqlmodel import text

                    with Session(engine) as session:
                        session.execute(
                            text(
                                "UPDATE change_aggregates SET status = 'FAILED', error_message = :error "
                                "WHERE id = :agg_id"
                            ),
                            {"agg_id": change_aggregate_id, "error": str(e)[:1000]},
                        )
                        session.commit()
                except Exception as db_error:
                    logfire.error("Failed to update DB", error=str(db_error))
                raise
    finally:
        logfire.force_flush()
