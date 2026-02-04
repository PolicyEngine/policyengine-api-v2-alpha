"""Seed UK datasets (FRS) and upload to S3.

NOTE: Requires HUGGING_FACE_TOKEN environment variable to be set,
as UK FRS datasets are hosted on a private HuggingFace repository.
"""

import argparse
import time
from pathlib import Path

import logfire
from rich.progress import Progress, SpinnerColumn, TextColumn
from sqlmodel import select

from seed_common import console, get_session


def main():
    parser = argparse.ArgumentParser(description="Seed UK datasets")
    parser.add_argument(
        "--lite",
        action="store_true",
        help="Lite mode: only seed FRS 2026",
    )
    args = parser.parse_args()

    # Import here to avoid slow import at module level
    from policyengine.tax_benefit_models.uk.datasets import (
        ensure_datasets as ensure_uk_datasets,
    )

    from policyengine_api.models import Dataset, TaxBenefitModel
    from policyengine_api.services.storage import upload_dataset_for_seeding

    console.print("[bold green]Seeding UK datasets...[/bold green]\n")
    console.print("[yellow]Note: Requires HUGGING_FACE_TOKEN environment variable[/yellow]\n")

    start = time.time()
    with get_session() as session:
        # Get UK model
        uk_model = session.exec(
            select(TaxBenefitModel).where(TaxBenefitModel.name == "policyengine-uk")
        ).first()

        if not uk_model:
            console.print("[red]Error: UK model not found. Run seed_uk_model.py first.[/red]")
            return

        data_folder = str(Path(__file__).parent.parent / "data")
        console.print(f"  Data folder: {data_folder}")

        # Get datasets
        console.print("  Loading UK datasets from policyengine package...")
        ds_start = time.time()
        uk_datasets = ensure_uk_datasets(data_folder=data_folder)
        console.print(f"  Loaded {len(uk_datasets)} datasets in {time.time() - ds_start:.1f}s")

        # In lite mode, only upload FRS 2026
        if args.lite:
            uk_datasets = {
                k: v for k, v in uk_datasets.items() if v.year == 2026 and "frs" in k
            }
            console.print(f"  Lite mode: filtered to {len(uk_datasets)} dataset(s)")

        created = 0
        skipped = 0

        with logfire.span("seed_uk_datasets", count=len(uk_datasets)):
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("UK datasets", total=len(uk_datasets))
                for name, pe_dataset in uk_datasets.items():
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
                    upload_start = time.time()
                    object_name = upload_dataset_for_seeding(pe_dataset.filepath)
                    console.print(f"    Uploaded {pe_dataset.name} in {time.time() - upload_start:.1f}s")

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

        console.print(f"[green]✓[/green] UK datasets: {created} created, {skipped} skipped")

    elapsed = time.time() - start
    console.print(f"\n[bold]Total time: {elapsed:.1f}s[/bold]")


if __name__ == "__main__":
    main()
