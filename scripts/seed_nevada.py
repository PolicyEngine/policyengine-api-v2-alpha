"""Seed Nevada datasets into local Supabase.

This script seeds pre-created Nevada state and congressional district datasets
into the local Supabase database for testing purposes.

Usage:
    uv run python scripts/seed_nevada.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rich.console import Console
from sqlmodel import Session, create_engine, select

from policyengine_api.config.settings import settings
from policyengine_api.models import Dataset, TaxBenefitModel
from policyengine_api.services.storage import upload_dataset_for_seeding

console = Console()

# Nevada datasets location
NEVADA_DATA_DIR = Path(__file__).parent.parent / "test_data" / "nevada_datasets"


def main():
    """Seed Nevada datasets."""
    console.print("[bold blue]Seeding Nevada datasets for testing...")

    engine = create_engine(settings.database_url, echo=False)

    with Session(engine) as session:
        # Get or create US model
        us_model = session.exec(
            select(TaxBenefitModel).where(TaxBenefitModel.name == "policyengine-us")
        ).first()

        if not us_model:
            console.print("  Creating US tax-benefit model...")
            us_model = TaxBenefitModel(
                name="policyengine-us",
                description="US tax-benefit system model",
            )
            session.add(us_model)
            session.commit()
            session.refresh(us_model)
            console.print("  [green]✓[/green] Created policyengine-us model")

        # Seed state datasets
        states_dir = NEVADA_DATA_DIR / "states"
        if states_dir.exists():
            console.print("\n  [bold]Nevada State Datasets:[/bold]")
            for h5_file in sorted(states_dir.glob("*.h5")):
                name = h5_file.stem  # e.g., "NV_year_2024"
                year = int(name.split("_")[-1])

                # Check if already exists
                existing = session.exec(
                    select(Dataset).where(Dataset.name == name)
                ).first()

                if existing:
                    console.print(f"    [yellow]⏭[/yellow] {name} (already exists)")
                    continue

                # Upload to storage
                console.print(f"    Uploading {name}...", end=" ")
                try:
                    object_name = upload_dataset_for_seeding(str(h5_file))

                    # Create database record
                    db_dataset = Dataset(
                        name=name,
                        description=f"Nevada state dataset for year {year}",
                        filepath=object_name,
                        year=year,
                        tax_benefit_model_id=us_model.id,
                    )
                    session.add(db_dataset)
                    session.commit()
                    console.print("[green]✓[/green]")
                except Exception as e:
                    console.print(f"[red]✗ {e}[/red]")

        # Seed district datasets
        districts_dir = NEVADA_DATA_DIR / "districts"
        if districts_dir.exists():
            console.print("\n  [bold]Nevada Congressional District Datasets:[/bold]")
            for h5_file in sorted(districts_dir.glob("*.h5")):
                name = h5_file.stem  # e.g., "NV-01_year_2024"
                year = int(name.split("_")[-1])
                district = name.split("_")[0]  # e.g., "NV-01"

                # Check if already exists
                existing = session.exec(
                    select(Dataset).where(Dataset.name == name)
                ).first()

                if existing:
                    console.print(f"    [yellow]⏭[/yellow] {name} (already exists)")
                    continue

                # Upload to storage
                console.print(f"    Uploading {name}...", end=" ")
                try:
                    object_name = upload_dataset_for_seeding(str(h5_file))

                    # Create database record
                    db_dataset = Dataset(
                        name=name,
                        description=f"{district} congressional district dataset for year {year}",
                        filepath=object_name,
                        year=year,
                        tax_benefit_model_id=us_model.id,
                    )
                    session.add(db_dataset)
                    session.commit()
                    console.print("[green]✓[/green]")
                except Exception as e:
                    console.print(f"[red]✗ {e}[/red]")

    console.print("\n[bold green]✓ Nevada datasets seeded successfully![/bold green]")


if __name__ == "__main__":
    main()
