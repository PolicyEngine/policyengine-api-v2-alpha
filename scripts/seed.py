"""Seed database with UK and US tax-benefit models, variables, parameters, and datasets."""

import sys
from pathlib import Path
import logging
import warnings

# Disable all SQLAlchemy and database logging BEFORE any imports
logging.basicConfig(level=logging.ERROR)
logging.getLogger('sqlalchemy').setLevel(logging.ERROR)
warnings.filterwarnings('ignore')

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from policyengine.tax_benefit_models.uk import uk_latest
from policyengine.tax_benefit_models.uk.datasets import ensure_datasets as ensure_uk_datasets
from policyengine.tax_benefit_models.us import us_latest
from policyengine.tax_benefit_models.us.datasets import ensure_datasets as ensure_us_datasets
from policyengine_api.models import (
    TaxBenefitModel,
    TaxBenefitModelVersion,
    Variable,
    Parameter,
    ParameterValue,
    Dataset,
)
from policyengine_api.services.storage import upload_dataset
from sqlmodel import Session, create_engine, select
from policyengine_api.config.settings import settings
from rich.console import Console
from rich.progress import track

console = Console()


def get_quiet_session():
    """Get database session with logging disabled."""
    engine = create_engine(settings.database_url, echo=False)
    with Session(engine) as session:
        yield session


def seed_model(model_version, session) -> TaxBenefitModelVersion:
    """Seed a tax-benefit model with its variables and parameters."""

    # Create or get the model
    console.print(f"[bold blue]Seeding {model_version.model.id}...")

    existing_model = session.exec(
        select(TaxBenefitModel).where(TaxBenefitModel.name == model_version.model.id)
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
        console.print(f"  Model version {model_version.version} already exists, skipping")
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
    console.print(f"  Adding {len(model_version.variables)} variables...")
    for var in track(model_version.variables, description="Variables"):
        db_var = Variable(
            name=var.name,
            entity=var.entity,
            description=var.description or "",
            data_type=var.data_type.__name__ if hasattr(var.data_type, '__name__') else str(var.data_type),
            tax_benefit_model_version_id=db_version.id,
        )
        session.add(db_var)

    session.commit()
    console.print(f"  [green]✓[/green] Added {len(model_version.variables)} variables")

    # Add parameters (creating a lookup for parameter values later)
    console.print(f"  Adding {len(model_version.parameters)} parameters...")
    param_id_map = {}  # Map from policyengine param id to db param id

    for param in track(model_version.parameters, description="Parameters"):
        db_param = Parameter(
            name=param.name,
            description=param.description or "",
            data_type=param.data_type.__name__ if hasattr(param.data_type, '__name__') else str(param.data_type),
            unit=param.unit,
            tax_benefit_model_version_id=db_version.id,
        )
        session.add(db_param)
        session.commit()
        session.refresh(db_param)
        param_id_map[param.id] = db_param.id

    console.print(f"  [green]✓[/green] Added {len(model_version.parameters)} parameters")

    # Add parameter values
    console.print(f"  Adding {len(model_version.parameter_values)} parameter values...")
    import math

    for pv in track(model_version.parameter_values, description="Parameter values"):
        if pv.parameter.id in param_id_map:
            # Handle Infinity values - skip them as they can't be stored in JSON
            if isinstance(pv.value, float) and (math.isinf(pv.value) or math.isnan(pv.value)):
                continue

            db_pv = ParameterValue(
                parameter_id=param_id_map[pv.parameter.id],
                value=pv.value,
                start_date=pv.start_date,
                end_date=pv.end_date,
            )
            session.add(db_pv)

    session.commit()
    console.print(f"  [green]✓[/green] Added {len(model_version.parameter_values)} parameter values")

    return db_version


def seed_datasets(session):
    """Seed datasets and upload to S3."""
    console.print("[bold blue]Seeding datasets...")

    # UK datasets
    console.print("  Creating UK datasets...")
    uk_datasets = ensure_uk_datasets()

    for _, pe_dataset in track(list(uk_datasets.items()), description="UK datasets"):
        # Check if dataset already exists
        existing = session.exec(
            select(Dataset).where(Dataset.name == pe_dataset.name)
        ).first()

        if existing:
            console.print(f"  Dataset {pe_dataset.name} already exists, skipping")
            continue

        # Upload to S3
        object_name = upload_dataset(pe_dataset.filepath)
        console.print(f"  Uploaded {pe_dataset.filepath} to S3 as {object_name}")

        # Create database record
        db_dataset = Dataset(
            name=pe_dataset.name,
            description=pe_dataset.description,
            filepath=object_name,  # Store S3 key, not local path
            year=pe_dataset.year,
            tax_benefit_model="uk_latest",
        )
        session.add(db_dataset)
        session.commit()
        console.print(f"  [green]✓[/green] Created dataset: {db_dataset.name}")

    # US datasets
    console.print("  Creating US datasets...")
    us_datasets = ensure_us_datasets()

    for _, pe_dataset in track(list(us_datasets.items()), description="US datasets"):
        # Check if dataset already exists
        existing = session.exec(
            select(Dataset).where(Dataset.name == pe_dataset.name)
        ).first()

        if existing:
            console.print(f"  Dataset {pe_dataset.name} already exists, skipping")
            continue

        # Upload to S3
        object_name = upload_dataset(pe_dataset.filepath)
        console.print(f"  Uploaded {pe_dataset.filepath} to S3 as {object_name}")

        # Create database record
        db_dataset = Dataset(
            name=pe_dataset.name,
            description=pe_dataset.description,
            filepath=object_name,  # Store S3 key, not local path
            year=pe_dataset.year,
            tax_benefit_model="us_latest",
        )
        session.add(db_dataset)
        session.commit()
        console.print(f"  [green]✓[/green] Created dataset: {db_dataset.name}")

    console.print(f"[green]✓[/green] Seeded {len(uk_datasets) + len(us_datasets)} datasets\n")


def main():
    """Main seed function."""
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

    console.print("\n[bold green]✓ Database seeding complete![/bold green]")


if __name__ == "__main__":
    main()
