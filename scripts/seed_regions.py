"""Seed regions for US and UK geographic analysis.

This script populates the regions table with:
- US: National, 51 states (incl. DC), 436 congressional districts, 333 places/cities
- UK: National and 4 countries (England, Scotland, Wales, Northern Ireland)

Regions are sourced from policyengine.py's region registries and linked
to the appropriate datasets in the database.

Usage:
    python scripts/seed_regions.py              # Seed all US and UK regions
    python scripts/seed_regions.py --us-only    # Seed only US regions
    python scripts/seed_regions.py --uk-only    # Seed only UK regions
    python scripts/seed_regions.py --skip-places     # Exclude US places (cities)
    python scripts/seed_regions.py --skip-districts  # Exclude US congressional districts
"""

import argparse
import time

from rich.progress import Progress, SpinnerColumn, TextColumn
from sqlmodel import Session, select

from seed_utils import console, get_session

# Import after seed_utils sets up path
from policyengine_api.models import Dataset, Region, TaxBenefitModel  # noqa: E402


def seed_us_regions(
    session: Session,
    skip_places: bool = False,
    skip_districts: bool = False,
) -> tuple[int, int]:
    """Seed US regions from policyengine.py registry.

    Args:
        session: Database session
        skip_places: Skip US places (cities over 100K population)
        skip_districts: Skip congressional districts

    Returns:
        Tuple of (created_count, skipped_count)
    """
    from policyengine.countries.us.regions import us_region_registry

    # Get US model
    us_model = session.exec(
        select(TaxBenefitModel).where(TaxBenefitModel.name == "policyengine-us")
    ).first()

    if not us_model:
        console.print("[red]Error: US model not found. Run seed.py first.[/red]")
        return 0, 0

    # Get US national dataset (CPS)
    us_dataset = session.exec(
        select(Dataset)
        .where(Dataset.tax_benefit_model_id == us_model.id)
        .where(Dataset.name.contains("cps"))  # type: ignore
        .order_by(Dataset.year.desc())  # type: ignore
    ).first()

    if not us_dataset:
        console.print("[red]Error: US dataset not found. Run seed.py first.[/red]")
        return 0, 0

    created = 0
    skipped = 0

    # Filter regions based on options
    regions_to_seed = []
    for region in us_region_registry.regions:
        if region.region_type == "national":
            regions_to_seed.append(region)
        elif region.region_type == "state":
            regions_to_seed.append(region)
        elif region.region_type == "congressional_district" and not skip_districts:
            regions_to_seed.append(region)
        elif region.region_type == "place" and not skip_places:
            regions_to_seed.append(region)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("US regions", total=len(regions_to_seed))

        for pe_region in regions_to_seed:
            progress.update(task, description=f"US: {pe_region.label}")

            # Check if region already exists
            existing = session.exec(
                select(Region).where(Region.code == pe_region.code)
            ).first()

            if existing:
                skipped += 1
                progress.advance(task)
                continue

            # Create region record
            db_region = Region(
                code=pe_region.code,
                label=pe_region.label,
                region_type=pe_region.region_type,
                requires_filter=pe_region.requires_filter,
                filter_field=pe_region.filter_field,
                filter_value=pe_region.filter_value,
                parent_code=pe_region.parent_code,
                state_code=pe_region.state_code,
                state_name=pe_region.state_name,
                dataset_id=us_dataset.id,  # All US regions use the national dataset
                tax_benefit_model_id=us_model.id,
            )
            session.add(db_region)
            created += 1
            progress.advance(task)

        session.commit()

    return created, skipped


def seed_uk_regions(session: Session) -> tuple[int, int]:
    """Seed UK regions from policyengine.py registry.

    Args:
        session: Database session

    Returns:
        Tuple of (created_count, skipped_count)
    """
    from policyengine.countries.uk.regions import uk_region_registry

    # Get UK model
    uk_model = session.exec(
        select(TaxBenefitModel).where(TaxBenefitModel.name == "policyengine-uk")
    ).first()

    if not uk_model:
        console.print(
            "[yellow]Warning: UK model not found. Skipping UK regions.[/yellow]"
        )
        return 0, 0

    # Get UK national dataset (FRS)
    uk_dataset = session.exec(
        select(Dataset)
        .where(Dataset.tax_benefit_model_id == uk_model.id)
        .where(Dataset.name.contains("frs"))  # type: ignore
        .order_by(Dataset.year.desc())  # type: ignore
    ).first()

    if not uk_dataset:
        console.print(
            "[yellow]Warning: UK dataset not found. Skipping UK regions.[/yellow]"
        )
        return 0, 0

    created = 0
    skipped = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("UK regions", total=len(uk_region_registry.regions))

        for pe_region in uk_region_registry.regions:
            progress.update(task, description=f"UK: {pe_region.label}")

            # Check if region already exists
            existing = session.exec(
                select(Region).where(Region.code == pe_region.code)
            ).first()

            if existing:
                skipped += 1
                progress.advance(task)
                continue

            # Create region record
            db_region = Region(
                code=pe_region.code,
                label=pe_region.label,
                region_type=pe_region.region_type,
                requires_filter=pe_region.requires_filter,
                filter_field=pe_region.filter_field,
                filter_value=pe_region.filter_value,
                parent_code=pe_region.parent_code,
                state_code=None,  # UK regions don't have state_code
                state_name=None,
                dataset_id=uk_dataset.id,  # All UK regions use the national dataset
                tax_benefit_model_id=uk_model.id,
            )
            session.add(db_region)
            created += 1
            progress.advance(task)

        session.commit()

    return created, skipped


def main():
    parser = argparse.ArgumentParser(description="Seed US and UK regions")
    parser.add_argument(
        "--us-only",
        action="store_true",
        help="Only seed US regions",
    )
    parser.add_argument(
        "--uk-only",
        action="store_true",
        help="Only seed UK regions",
    )
    parser.add_argument(
        "--skip-places",
        action="store_true",
        help="Skip US places (cities over 100K population)",
    )
    parser.add_argument(
        "--skip-districts",
        action="store_true",
        help="Skip US congressional districts",
    )
    args = parser.parse_args()

    console.print("[bold green]Seeding regions...[/bold green]\n")

    start = time.time()
    total_created = 0
    total_skipped = 0

    with get_session() as session:
        # Seed US regions
        if not args.uk_only:
            console.print("[bold]US Regions[/bold]")
            us_created, us_skipped = seed_us_regions(
                session,
                skip_places=args.skip_places,
                skip_districts=args.skip_districts,
            )
            total_created += us_created
            total_skipped += us_skipped
            console.print(
                f"[green]✓[/green] US regions: {us_created} created, {us_skipped} skipped\n"
            )

        # Seed UK regions
        if not args.us_only:
            console.print("[bold]UK Regions[/bold]")
            uk_created, uk_skipped = seed_uk_regions(session)
            total_created += uk_created
            total_skipped += uk_skipped
            console.print(
                f"[green]✓[/green] UK regions: {uk_created} created, {uk_skipped} skipped\n"
            )

    elapsed = time.time() - start
    console.print(f"[bold]Total: {total_created} created, {total_skipped} skipped[/bold]")
    console.print(f"[bold]Time: {elapsed:.1f}s[/bold]")


if __name__ == "__main__":
    main()
