"""Shared utilities for seed scripts."""

import io
import json
import logging
import math
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import logfire
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from sqlmodel import Session, create_engine

# Disable all SQLAlchemy and database logging BEFORE any imports
logging.basicConfig(level=logging.ERROR)
logging.getLogger("sqlalchemy").setLevel(logging.ERROR)
warnings.filterwarnings("ignore")

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from policyengine_api.config.settings import settings  # noqa: E402

# Configure logfire
if settings.logfire_token:
    logfire.configure(
        token=settings.logfire_token,
        environment=settings.logfire_environment,
        console=False,
    )

console = Console()


def get_session():
    """Get database session with logging disabled."""
    engine = create_engine(settings.database_url, echo=False)
    return Session(engine)


def bulk_insert(session, table: str, columns: list[str], rows: list[dict]):
    """Fast bulk insert using PostgreSQL COPY via StringIO."""
    if not rows:
        return

    # Get raw psycopg2 connection
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
    session.commit()


def seed_model(model_version, session, lite: bool = False):
    """Seed a tax-benefit model with its variables and parameters.

    Args:
        model_version: The policyengine package model version
        session: Database session
        lite: If True, skip state-level parameters

    Returns the TaxBenefitModelVersion that was created or found.
    """
    from policyengine_api.models import (
        TaxBenefitModel,
        TaxBenefitModelVersion,
    )
    from sqlmodel import select

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
                    # default_value is pre-serialized by policyengine.py:
                    # - Enum values are converted to their name (e.g., "SINGLE")
                    # - datetime.date values are converted to ISO format
                    # - Primitives (bool, int, float, str) are kept as-is
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
                            "default_value": json.dumps(var.default_value),
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
                    "default_value",
                    "tax_benefit_model_version_id",
                    "created_at",
                ],
                var_rows,
            )

            console.print(
                f"  [green]✓[/green] Added {len(model_version.variables)} variables"
            )

        # Add parameters - deduplicate by name (keep first occurrence)
        #
        # WHY DEDUPLICATION IS NEEDED:
        # The policyengine package can provide multiple parameter entries with the same
        # name. This happens because parameters can have multiple bracket entries or
        # state-specific variants that share the same base name. We keep only the first
        # occurrence to avoid database unique constraint violations and reduce redundancy.
        #
        # NOTE: We do NOT filter by label. Parameters without labels (bracket params,
        # breakdown params) are still valid and needed for policy analysis.
        #
        # In lite mode, exclude US state parameters (gov.states.*)
        seen_names = set()
        parameters_to_add = []
        skipped_state_params = 0
        skipped_duplicate = 0

        for p in model_version.parameters:
            if p.name in seen_names:
                skipped_duplicate += 1
                continue
            # In lite mode, skip state-level parameters for faster seeding
            if lite and p.name.startswith("gov.states."):
                skipped_state_params += 1
                continue
            parameters_to_add.append(p)
            seen_names.add(p.name)

        console.print(f"  Parameter filtering:")
        console.print(f"    - Total from source: {len(model_version.parameters)}")
        console.print(f"    - Skipped (duplicate name): {skipped_duplicate}")
        if lite and skipped_state_params > 0:
            console.print(f"    - Skipped (state params, lite mode): {skipped_state_params}")
        console.print(f"    - To add: {len(parameters_to_add)}")

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

                    # Source data has dates swapped (start > end), fix ordering
                    # Only swap if both dates are set, otherwise keep original
                    if pv.start_date and pv.end_date:
                        start = pv.end_date  # Swap: source end is our start
                        end = pv.start_date  # Swap: source start is our end
                    else:
                        start = pv.start_date
                        end = pv.end_date
                    pv_rows.append(
                        {
                            "id": uuid4(),
                            "parameter_id": param_id_map[pv.parameter.id],
                            "value_json": json.dumps(pv.value),
                            "start_date": start,
                            "end_date": end,
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
