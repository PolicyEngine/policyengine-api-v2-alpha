"""Seed tax-benefit models with variables and parameters.

This script seeds TaxBenefitModel, TaxBenefitModelVersion, Variables,
Parameters, and ParameterValues from policyengine.py.

Usage:
    python scripts/seed_models.py              # Seed UK and US models
    python scripts/seed_models.py --us-only    # Seed only US model
    python scripts/seed_models.py --uk-only    # Seed only UK model
    python scripts/seed_models.py --skip-state-params  # Skip US state parameters
"""

import argparse
import json
import math
from datetime import datetime, timezone
from uuid import uuid4

import logfire
import yaml
from policyengine_uk import CountryTaxBenefitSystem as UKTaxBenefitSystem
from policyengine_us import CountryTaxBenefitSystem as USTaxBenefitSystem
from rich.progress import Progress, SpinnerColumn, TextColumn
from seed_utils import bulk_insert, console, get_session
from sqlmodel import Session, select

# Import after seed_utils sets up path
from policyengine_api.models import (  # noqa: E402
    TaxBenefitModel,
    TaxBenefitModelVersion,
)


def get_modelled_policies(model_name: str) -> dict | None:
    """Extract modelled_policies from country package.

    Args:
        model_name: The model name (e.g., "policyengine-us", "policyengine-uk")

    Returns:
        The modelled_policies dict, or None if not available.
    """
    try:
        if model_name == "policyengine-us":
            system = USTaxBenefitSystem()
            # US system loads modelled_policies as dict during init
            if isinstance(system.modelled_policies, dict):
                return system.modelled_policies
            return None
        elif model_name == "policyengine-uk":
            system = UKTaxBenefitSystem()
            # UK system keeps modelled_policies as a Path, need to load YAML
            if system.modelled_policies and hasattr(
                system.modelled_policies, "read_text"
            ):
                with open(system.modelled_policies, "r") as f:
                    return yaml.safe_load(f)
            elif isinstance(system.modelled_policies, dict):
                return system.modelled_policies
            return None
        else:
            return None
    except Exception as e:
        console.print(
            f"  [yellow]Warning: Could not load modelled_policies: {e}[/yellow]"
        )
        return None


def seed_model(
    model_version,
    session: Session,
    skip_state_params: bool = False,
    variable_whitelist: set[str] | None = None,
    parameter_prefixes: set[str] | None = None,
) -> TaxBenefitModelVersion:
    """Seed a tax-benefit model with its variables and parameters.

    Args:
        model_version: The policyengine.py model version object
        session: Database session
        skip_state_params: Skip US state-level parameters (gov.states.*)
        variable_whitelist: If provided, only seed variables whose name is in this set
        parameter_prefixes: If provided, only seed parameters whose name starts with
            one of these prefixes

    Returns:
        The created or existing TaxBenefitModelVersion
    """
    with logfire.span(
        "seed_model",
        model=model_version.model.id,
        version=model_version.version,
    ):
        console.print(f"[bold blue]Seeding {model_version.model.id}...")

        # Create or get the model
        existing_model = session.exec(
            select(TaxBenefitModel).where(
                TaxBenefitModel.name == model_version.model.id
            )
        ).first()

        # Get modelled_policies from country package
        modelled_policies = get_modelled_policies(model_version.model.id)
        if modelled_policies:
            console.print(f"  Loaded modelled_policies for {model_version.model.id}")

        if existing_model:
            db_model = existing_model
            # Update modelled_policies if not already set
            if modelled_policies and not db_model.modelled_policies:
                db_model.modelled_policies = modelled_policies
                session.add(db_model)
                session.commit()
                console.print(
                    f"  Updated modelled_policies for existing model: {db_model.id}"
                )
            else:
                console.print(f"  Using existing model: {db_model.id}")
        else:
            db_model = TaxBenefitModel(
                name=model_version.model.id,
                description=model_version.model.description,
                modelled_policies=modelled_policies,
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

        # Filter variables by whitelist if provided
        variables = model_version.variables
        if variable_whitelist is not None:
            variables = [v for v in variables if v.name in variable_whitelist]
            console.print(
                f"  Filtered to {len(variables)} variables "
                f"(from {len(model_version.variables)} total, whitelist applied)"
            )

        # Add variables
        with logfire.span("add_variables", count=len(variables)):
            var_rows = []
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    f"Preparing {len(variables)} variables",
                    total=len(variables),
                )
                for var in variables:
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
                f"  [green]✓[/green] Added {len(variables)} variables"
            )

        # Add parameters (only user-facing ones: those with labels)
        # Deduplicate by name - keep first occurrence
        seen_names = set()
        parameters_to_add = []
        skipped_state_params_count = 0
        skipped_prefix_count = 0
        for p in model_version.parameters:
            if p.label is None or p.name in seen_names:
                continue
            # Skip state-level parameters if requested
            if skip_state_params and p.name.startswith("gov.states."):
                skipped_state_params_count += 1
                continue
            # Skip parameters not matching prefix whitelist
            if parameter_prefixes is not None and not any(
                p.name.startswith(prefix) for prefix in parameter_prefixes
            ):
                skipped_prefix_count += 1
                continue
            parameters_to_add.append(p)
            seen_names.add(p.name)

        filter_msg = f"  Filtered to {len(parameters_to_add)} user-facing parameters"
        filter_msg += (
            f" (from {len(model_version.parameters)} total, deduplicated by name)"
        )
        if skip_state_params and skipped_state_params_count > 0:
            filter_msg += f", skipped {skipped_state_params_count} state params"
        if parameter_prefixes is not None and skipped_prefix_count > 0:
            filter_msg += f", skipped {skipped_prefix_count} by prefix filter"
        console.print(filter_msg)

        with logfire.span("add_parameters", count=len(parameters_to_add)):
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


def seed_uk_model(
    session: Session,
    skip_state_params: bool = False,
    variable_whitelist: set[str] | None = None,
    parameter_prefixes: set[str] | None = None,
):
    """Seed UK model."""
    from policyengine.tax_benefit_models.uk import uk_latest

    version = seed_model(
        uk_latest,
        session,
        skip_state_params=skip_state_params,
        variable_whitelist=variable_whitelist,
        parameter_prefixes=parameter_prefixes,
    )
    console.print(f"[green]✓[/green] UK model seeded: {version.id}\n")
    return version


def seed_us_model(
    session: Session,
    skip_state_params: bool = False,
    variable_whitelist: set[str] | None = None,
    parameter_prefixes: set[str] | None = None,
):
    """Seed US model."""
    from policyengine.tax_benefit_models.us import us_latest

    version = seed_model(
        us_latest,
        session,
        skip_state_params=skip_state_params,
        variable_whitelist=variable_whitelist,
        parameter_prefixes=parameter_prefixes,
    )
    console.print(f"[green]✓[/green] US model seeded: {version.id}\n")
    return version


def main():
    parser = argparse.ArgumentParser(description="Seed tax-benefit models")
    parser.add_argument(
        "--us-only",
        action="store_true",
        help="Only seed US model",
    )
    parser.add_argument(
        "--uk-only",
        action="store_true",
        help="Only seed UK model",
    )
    parser.add_argument(
        "--skip-state-params",
        action="store_true",
        help="Skip US state-level parameters (gov.states.*)",
    )
    args = parser.parse_args()

    console.print("[bold green]Seeding tax-benefit models...[/bold green]\n")

    with get_session() as session:
        if not args.us_only:
            seed_uk_model(session, skip_state_params=args.skip_state_params)

        if not args.uk_only:
            seed_us_model(session, skip_state_params=args.skip_state_params)

    console.print("[bold green]✓ Model seeding complete![/bold green]")


if __name__ == "__main__":
    main()
