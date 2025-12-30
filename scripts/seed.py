"""Seed database with UK and US models, variables, parameters, datasets."""

import json
import logging
import math
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import logfire

# Disable all SQLAlchemy and database logging BEFORE any imports
logging.basicConfig(level=logging.ERROR)
logging.getLogger("sqlalchemy").setLevel(logging.ERROR)
warnings.filterwarnings("ignore")

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from policyengine.tax_benefit_models.uk import uk_latest  # noqa: E402
from policyengine.tax_benefit_models.uk.datasets import (  # noqa: E402
    ensure_datasets as ensure_uk_datasets,
)
from policyengine.tax_benefit_models.us import us_latest  # noqa: E402
from policyengine.tax_benefit_models.us.datasets import (  # noqa: E402
    ensure_datasets as ensure_us_datasets,
)
from rich.console import Console  # noqa: E402
from rich.progress import Progress, SpinnerColumn, TextColumn  # noqa: E402
from sqlmodel import Session, create_engine, select  # noqa: E402

from policyengine_api.config.settings import settings  # noqa: E402
from policyengine_api.models import (  # noqa: E402
    Dataset,
    Parameter,
    ParameterValue,
    Policy,
    TaxBenefitModel,
    TaxBenefitModelVersion,
)
from policyengine_api.services.storage import (  # noqa: E402
    upload_dataset_for_seeding,
)

# Configure logfire
if settings.logfire_token:
    logfire.configure(
        token=settings.logfire_token,
        environment=settings.logfire_environment,
        console=False,
    )

console = Console()


def get_quiet_session():
    """Get database session with logging disabled."""
    engine = create_engine(settings.database_url, echo=False)
    with Session(engine) as session:
        yield session


def bulk_insert(session, table: str, columns: list[str], rows: list[dict]):
    """Fast bulk insert using PostgreSQL COPY via StringIO."""
    if not rows:
        return

    import io

    # Get raw psycopg2 connection - need to use the connection from session
    # but not commit separately to avoid transaction issues
    connection = session.connection()
    raw_conn = connection.connection.dbapi_connection
    cursor = raw_conn.cursor()

    # Build CSV-like data in memory
    output = io.StringIO()
    for row in rows:
        values = []
        for col in columns:
            val = row[col]
            if val is None:
                values.append("\\N")
            elif isinstance(val, str):
                # Escape special characters for COPY
                val = (
                    val.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n")
                )
                values.append(val)
            else:
                values.append(str(val))
        output.write("\t".join(values) + "\n")

    output.seek(0)

    # COPY is the fastest way to bulk load PostgreSQL
    cursor.copy_from(output, table, columns=columns, null="\\N")
    # Let SQLAlchemy handle the commit via session
    session.commit()


def seed_model(model_version, session) -> TaxBenefitModelVersion:
    """Seed a tax-benefit model with its variables and parameters."""

    with logfire.span(
        "seed_model",
        model=model_version.model.id,
        version=model_version.version,
    ):
        # Create or get the model
        console.print(f"[bold blue]Seeding {model_version.model.id}...")

        existing_model = session.exec(
            select(TaxBenefitModel).where(
                TaxBenefitModel.name == model_version.model.id
            )
        ).first()

        if existing_model:
            db_model = existing_model
            console.print(f"  Using existing model: {db_model.id}")
        else:
            db_model = TaxBenefitModel(
                name=model_version.model.id,
                description=model_version.model.description,
            )
            session.add(db_model)
            session.commit()
            session.refresh(db_model)
            console.print(f"  Created model: {db_model.id}")

        # Create model version
        existing_version = session.exec(
            select(TaxBenefitModelVersion).where(
                TaxBenefitModelVersion.model_id == db_model.id,
                TaxBenefitModelVersion.version == model_version.version,
            )
        ).first()

        if existing_version:
            console.print(
                f"  Model version {model_version.version} already exists, skipping"
            )
            return existing_version

        db_version = TaxBenefitModelVersion(
            model_id=db_model.id,
            version=model_version.version,
            description=f"Version {model_version.version}",
        )
        session.add(db_version)
        session.commit()
        session.refresh(db_version)
        console.print(f"  Created version: {db_version.version}")

        # Add variables
        with logfire.span("add_variables", count=len(model_version.variables)):
            var_rows = []
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    f"Preparing {len(model_version.variables)} variables",
                    total=len(model_version.variables),
                )
                for var in model_version.variables:
                    var_rows.append(
                        {
                            "id": uuid4(),
                            "name": var.name,
                            "entity": var.entity,
                            "description": var.description or "",
                            "data_type": var.data_type.__name__
                            if hasattr(var.data_type, "__name__")
                            else str(var.data_type),
                            "possible_values": None,
                            "tax_benefit_model_version_id": db_version.id,
                            "created_at": datetime.now(timezone.utc),
                        }
                    )
                    progress.advance(task)

            console.print(f"  Inserting {len(var_rows)} variables...")
            bulk_insert(
                session,
                "variables",
                [
                    "id",
                    "name",
                    "entity",
                    "description",
                    "data_type",
                    "possible_values",
                    "tax_benefit_model_version_id",
                    "created_at",
                ],
                var_rows,
            )

            console.print(
                f"  [green]✓[/green] Added {len(model_version.variables)} variables"
            )

        # Add parameters (only user-facing ones: those with labels or gov.* params)
        # Deduplicate by name - keep first occurrence
        seen_names = set()
        parameters_to_add = []
        for p in model_version.parameters:
            if p.label is not None and p.name not in seen_names:
                parameters_to_add.append(p)
                seen_names.add(p.name)
        console.print(
            f"  Filtered to {len(parameters_to_add)} user-facing parameters "
            f"(from {len(model_version.parameters)} total, deduplicated by name)"
        )

        with logfire.span("add_parameters", count=len(parameters_to_add)):
            # Build list of parameter dicts for bulk insert
            param_rows = []
            param_names = []  # Track (pe_id, name, generated_uuid)

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    f"Preparing {len(parameters_to_add)} parameters",
                    total=len(parameters_to_add),
                )
                for param in parameters_to_add:
                    param_uuid = uuid4()
                    param_rows.append(
                        {
                            "id": param_uuid,
                            "name": param.name,
                            "label": param.label if hasattr(param, "label") else None,
                            "description": param.description or "",
                            "data_type": param.data_type.__name__
                            if hasattr(param.data_type, "__name__")
                            else str(param.data_type),
                            "unit": param.unit,
                            "tax_benefit_model_version_id": db_version.id,
                            "created_at": datetime.now(timezone.utc),
                        }
                    )
                    param_names.append((param.id, param.name, param_uuid))
                    progress.advance(task)

            console.print(f"  Inserting {len(param_rows)} parameters...")
            bulk_insert(
                session,
                "parameters",
                [
                    "id",
                    "name",
                    "label",
                    "description",
                    "data_type",
                    "unit",
                    "tax_benefit_model_version_id",
                    "created_at",
                ],
                param_rows,
            )

            # Build param_id_map from pre-generated UUIDs
            param_id_map = {pe_id: db_uuid for pe_id, name, db_uuid in param_names}

            console.print(
                f"  [green]✓[/green] Added {len(parameters_to_add)} parameters"
            )

        # Add parameter values
        # Filter to only include values for parameters we added
        parameter_values_to_add = [
            pv
            for pv in model_version.parameter_values
            if pv.parameter.id in param_id_map
        ]
        console.print(f"  Found {len(parameter_values_to_add)} parameter values to add")

        with logfire.span("add_parameter_values", count=len(parameter_values_to_add)):
            pv_rows = []
            skipped = 0

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    f"Preparing {len(parameter_values_to_add)} parameter values",
                    total=len(parameter_values_to_add),
                )
                for pv in parameter_values_to_add:
                    # Handle Infinity values - skip them as they can't be stored in JSON
                    if isinstance(pv.value, float) and (
                        math.isinf(pv.value) or math.isnan(pv.value)
                    ):
                        skipped += 1
                        progress.advance(task)
                        continue

                    pv_rows.append(
                        {
                            "id": uuid4(),
                            "parameter_id": param_id_map[pv.parameter.id],
                            "value_json": json.dumps(pv.value),
                            "start_date": pv.start_date,
                            "end_date": pv.end_date,
                            "policy_id": None,
                            "dynamic_id": None,
                            "created_at": datetime.now(timezone.utc),
                        }
                    )
                    progress.advance(task)

            console.print(f"  Inserting {len(pv_rows)} parameter values...")
            bulk_insert(
                session,
                "parameter_values",
                [
                    "id",
                    "parameter_id",
                    "value_json",
                    "start_date",
                    "end_date",
                    "policy_id",
                    "dynamic_id",
                    "created_at",
                ],
                pv_rows,
            )

            console.print(
                f"  [green]✓[/green] Added {len(pv_rows)} parameter values"
                + (f" (skipped {skipped} invalid)" if skipped else "")
            )

        return db_version


def seed_datasets(session):
    """Seed datasets and upload to S3."""
    with logfire.span("seed_datasets"):
        console.print("[bold blue]Seeding datasets...")

        # Get UK and US models
        uk_model = session.exec(
            select(TaxBenefitModel).where(TaxBenefitModel.name == "policyengine-uk")
        ).first()
        us_model = session.exec(
            select(TaxBenefitModel).where(TaxBenefitModel.name == "policyengine-us")
        ).first()

        if not uk_model or not us_model:
            console.print(
                "[red]Error: UK or US model not found. Run seed_model first.[/red]"
            )
            return

        # UK datasets
        console.print("  Creating UK datasets...")
        uk_datasets = ensure_uk_datasets()
        uk_created = 0
        uk_skipped = 0

        with logfire.span("seed_uk_datasets", count=len(uk_datasets)):
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("UK datasets", total=len(uk_datasets))
                for _, pe_dataset in uk_datasets.items():
                    progress.update(task, description=f"UK: {pe_dataset.name}")

                    # Check if dataset already exists
                    existing = session.exec(
                        select(Dataset).where(Dataset.name == pe_dataset.name)
                    ).first()

                    if existing:
                        uk_skipped += 1
                        progress.advance(task)
                        continue

                    # Upload to S3
                    object_name = upload_dataset_for_seeding(pe_dataset.filepath)

                    # Create database record
                    db_dataset = Dataset(
                        name=pe_dataset.name,
                        description=pe_dataset.description,
                        filepath=object_name,
                        year=pe_dataset.year,
                        tax_benefit_model_id=uk_model.id,
                    )
                    session.add(db_dataset)
                    session.commit()
                    uk_created += 1
                    progress.advance(task)

        console.print(
            f"  [green]✓[/green] UK: {uk_created} created, {uk_skipped} skipped"
        )

        # US datasets
        console.print("  Creating US datasets...")
        us_datasets = ensure_us_datasets()
        us_created = 0
        us_skipped = 0

        with logfire.span("seed_us_datasets", count=len(us_datasets)):
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("US datasets", total=len(us_datasets))
                for _, pe_dataset in us_datasets.items():
                    progress.update(task, description=f"US: {pe_dataset.name}")

                    # Check if dataset already exists
                    existing = session.exec(
                        select(Dataset).where(Dataset.name == pe_dataset.name)
                    ).first()

                    if existing:
                        us_skipped += 1
                        progress.advance(task)
                        continue

                    # Upload to S3
                    object_name = upload_dataset_for_seeding(pe_dataset.filepath)

                    # Create database record
                    db_dataset = Dataset(
                        name=pe_dataset.name,
                        description=pe_dataset.description,
                        filepath=object_name,
                        year=pe_dataset.year,
                        tax_benefit_model_id=us_model.id,
                    )
                    session.add(db_dataset)
                    session.commit()
                    us_created += 1
                    progress.advance(task)

        console.print(
            f"  [green]✓[/green] US: {us_created} created, {us_skipped} skipped"
        )
        console.print(
            f"[green]✓[/green] Seeded {uk_created + us_created} datasets total\n"
        )


def seed_example_policies(session):
    """Seed example policy reforms for UK and US."""
    with logfire.span("seed_example_policies"):
        console.print("[bold blue]Seeding example policies...")

        # Get model versions
        uk_model = session.exec(
            select(TaxBenefitModel).where(TaxBenefitModel.name == "policyengine-uk")
        ).first()
        us_model = session.exec(
            select(TaxBenefitModel).where(TaxBenefitModel.name == "policyengine-us")
        ).first()

        if not uk_model or not us_model:
            console.print(
                "[red]Error: UK or US model not found. Run seed_model first.[/red]"
            )
            return

        uk_version = session.exec(
            select(TaxBenefitModelVersion)
            .where(TaxBenefitModelVersion.model_id == uk_model.id)
            .order_by(TaxBenefitModelVersion.created_at.desc())
        ).first()

        us_version = session.exec(
            select(TaxBenefitModelVersion)
            .where(TaxBenefitModelVersion.model_id == us_model.id)
            .order_by(TaxBenefitModelVersion.created_at.desc())
        ).first()

        # UK example policy: raise basic rate to 22p
        uk_policy_name = "UK basic rate 22p"
        existing_uk_policy = session.exec(
            select(Policy).where(Policy.name == uk_policy_name)
        ).first()

        if existing_uk_policy:
            console.print(f"  Policy '{uk_policy_name}' already exists, skipping")
        else:
            # Find the basic rate parameter
            uk_basic_rate_param = session.exec(
                select(Parameter).where(
                    Parameter.name == "gov.hmrc.income_tax.rates.uk[0].rate",
                    Parameter.tax_benefit_model_version_id == uk_version.id,
                )
            ).first()

            if uk_basic_rate_param:
                uk_policy = Policy(
                    name=uk_policy_name,
                    description="Raise the UK income tax basic rate from 20p to 22p",
                )
                session.add(uk_policy)
                session.commit()
                session.refresh(uk_policy)

                # Add parameter value (22% = 0.22)
                uk_param_value = ParameterValue(
                    parameter_id=uk_basic_rate_param.id,
                    value_json={"value": 0.22},
                    start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    end_date=None,
                    policy_id=uk_policy.id,
                )
                session.add(uk_param_value)
                session.commit()
                console.print(f"  [green]✓[/green] Created UK policy: {uk_policy_name}")
            else:
                console.print(
                    "  [yellow]Warning: UK basic rate parameter not found[/yellow]"
                )

        # US example policy: raise first bracket rate to 12%
        us_policy_name = "US 12% lowest bracket"
        existing_us_policy = session.exec(
            select(Policy).where(Policy.name == us_policy_name)
        ).first()

        if existing_us_policy:
            console.print(f"  Policy '{us_policy_name}' already exists, skipping")
        else:
            # Find the first bracket rate parameter
            us_first_bracket_param = session.exec(
                select(Parameter).where(
                    Parameter.name == "gov.irs.income.bracket.rates.1",
                    Parameter.tax_benefit_model_version_id == us_version.id,
                )
            ).first()

            if us_first_bracket_param:
                us_policy = Policy(
                    name=us_policy_name,
                    description="Raise US federal income tax lowest bracket to 12%",
                )
                session.add(us_policy)
                session.commit()
                session.refresh(us_policy)

                # Add parameter value (12% = 0.12)
                us_param_value = ParameterValue(
                    parameter_id=us_first_bracket_param.id,
                    value_json={"value": 0.12},
                    start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    end_date=None,
                    policy_id=us_policy.id,
                )
                session.add(us_param_value)
                session.commit()
                console.print(f"  [green]✓[/green] Created US policy: {us_policy_name}")
            else:
                console.print(
                    "  [yellow]Warning: US first bracket parameter not found[/yellow]"
                )

        console.print("[green]✓[/green] Example policies seeded\n")


def main():
    """Main seed function."""
    with logfire.span("database_seeding"):
        console.print("[bold green]PolicyEngine database seeding[/bold green]\n")

        with next(get_quiet_session()) as session:
            # Seed UK model
            uk_version = seed_model(uk_latest, session)
            console.print(f"[green]✓[/green] UK model seeded: {uk_version.id}\n")

            # Seed US model
            us_version = seed_model(us_latest, session)
            console.print(f"[green]✓[/green] US model seeded: {us_version.id}\n")

            # Seed datasets
            seed_datasets(session)

            # Seed example policies
            seed_example_policies(session)

        console.print("\n[bold green]✓ Database seeding complete![/bold green]")


if __name__ == "__main__":
    main()
