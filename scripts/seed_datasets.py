"""Seed datasets and upload to S3.

This script downloads datasets from policyengine.py, uploads them to S3,
and creates database records.

Usage:
    python scripts/seed_datasets.py              # Seed UK and US datasets
    python scripts/seed_datasets.py --us-only    # Seed only US datasets
    python scripts/seed_datasets.py --uk-only    # Seed only UK datasets
    python scripts/seed_datasets.py --year=2026  # Seed only 2026 datasets
"""

import argparse
from pathlib import Path

import logfire
from rich.progress import Progress, SpinnerColumn, TextColumn
from seed_utils import console, get_session
from sqlmodel import Session, select

# Import after seed_utils sets up path
from policyengine_api.models import Dataset, TaxBenefitModel  # noqa: E402
from policyengine_api.services.storage import upload_dataset_for_seeding  # noqa: E402


def seed_uk_datasets(session: Session, year: int | None = None) -> tuple[int, int]:
    """Seed UK datasets.

    Args:
        session: Database session
        year: If specified, only seed datasets for this year

    Returns:
        Tuple of (created_count, skipped_count)
    """
    from policyengine.tax_benefit_models.uk.datasets import (
        ensure_datasets as ensure_uk_datasets,
    )

    uk_model = session.exec(
        select(TaxBenefitModel).where(TaxBenefitModel.name == "policyengine-uk")
    ).first()

    if not uk_model:
        console.print("[red]Error: UK model not found. Run seed_models.py first.[/red]")
        return 0, 0

    data_folder = str(Path(__file__).parent.parent / "data")
    uk_datasets = ensure_uk_datasets(data_folder=data_folder)

    # Filter by year if specified
    if year:
        uk_datasets = {
            k: v for k, v in uk_datasets.items() if v.year == year and "frs" in k
        }
        console.print(f"  Filtered to {len(uk_datasets)} dataset(s) for year {year}")

    created = 0
    skipped = 0

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
                    skipped += 1
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
                created += 1
                progress.advance(task)

    return created, skipped


def seed_us_datasets(session: Session, year: int | None = None) -> tuple[int, int]:
    """Seed US datasets.

    Args:
        session: Database session
        year: If specified, only seed datasets for this year

    Returns:
        Tuple of (created_count, skipped_count)
    """
    from policyengine.tax_benefit_models.us.datasets import (
        ensure_datasets as ensure_us_datasets,
    )

    us_model = session.exec(
        select(TaxBenefitModel).where(TaxBenefitModel.name == "policyengine-us")
    ).first()

    if not us_model:
        console.print("[red]Error: US model not found. Run seed_models.py first.[/red]")
        return 0, 0

    data_folder = str(Path(__file__).parent.parent / "data")
    us_datasets = ensure_us_datasets(data_folder=data_folder)

    # Filter by year if specified
    if year:
        us_datasets = {
            k: v for k, v in us_datasets.items() if v.year == year and "cps" in k
        }
        console.print(f"  Filtered to {len(us_datasets)} dataset(s) for year {year}")

    created = 0
    skipped = 0

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
                    skipped += 1
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
                created += 1
                progress.advance(task)

    return created, skipped


def main():
    parser = argparse.ArgumentParser(description="Seed datasets")
    parser.add_argument(
        "--us-only",
        action="store_true",
        help="Only seed US datasets",
    )
    parser.add_argument(
        "--uk-only",
        action="store_true",
        help="Only seed UK datasets",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Only seed datasets for this year (e.g., 2026)",
    )
    args = parser.parse_args()

    year_str = f" (year {args.year})" if args.year else ""
    console.print(f"[bold green]Seeding datasets{year_str}...[/bold green]\n")

    total_created = 0
    total_skipped = 0

    with get_session() as session:
        if not args.us_only:
            console.print("[bold]UK Datasets[/bold]")
            uk_created, uk_skipped = seed_uk_datasets(session, year=args.year)
            total_created += uk_created
            total_skipped += uk_skipped
            console.print(
                f"[green]✓[/green] UK: {uk_created} created, {uk_skipped} skipped\n"
            )

        if not args.uk_only:
            console.print("[bold]US Datasets[/bold]")
            us_created, us_skipped = seed_us_datasets(session, year=args.year)
            total_created += us_created
            total_skipped += us_skipped
            console.print(
                f"[green]✓[/green] US: {us_created} created, {us_skipped} skipped\n"
            )

    console.print(
        f"[bold green]✓ Dataset seeding complete! "
        f"{total_created} created, {total_skipped} skipped[/bold green]"
    )


if __name__ == "__main__":
    main()
