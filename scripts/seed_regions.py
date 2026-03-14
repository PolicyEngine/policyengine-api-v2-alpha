"""Seed regions for US and UK geographic analysis.

This script populates the regions table with:
- US: National, 51 states (incl. DC), 436 congressional districts, 333 places/cities
- UK: National and 4 countries (England, Scotland, Wales, Northern Ireland)

Regions are sourced from policyengine.py's region registries and linked
to the appropriate datasets via the region_datasets join table.

This script is the SOLE source of truth for region-to-dataset wiring.
After importing datasets with import_state_datasets.py, re-run this script
to link regions to any newly available datasets.

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
from seed_utils import console, get_session
from sqlmodel import Session, select

# Import after seed_utils sets up path
from policyengine_api.models import (  # noqa: E402
    Dataset,
    Region,
    RegionDatasetLink,
    TaxBenefitModel,
)
from policyengine_api.models.region import RegionType  # noqa: E402


def _group_us_datasets(
    session: Session,
    us_model_id,
) -> tuple[list[Dataset], dict[str, list[Dataset]], dict[str, list[Dataset]]]:
    """Pre-fetch and group all US datasets by type.

    Returns:
        (national_datasets, state_datasets_by_code, district_datasets_by_code)
    """
    all_datasets = session.exec(
        select(Dataset).where(Dataset.tax_benefit_model_id == us_model_id)
    ).all()

    national = []
    by_state: dict[str, list[Dataset]] = {}
    by_district: dict[str, list[Dataset]] = {}

    for d in all_datasets:
        if d.filepath and d.filepath.startswith("states/"):
            # filepath = "states/AL/AL-year-2024.h5"
            parts = d.filepath.split("/")
            if len(parts) >= 2:
                by_state.setdefault(parts[1], []).append(d)
        elif d.filepath and d.filepath.startswith("districts/"):
            # filepath = "districts/AL-01/AL-01-year-2024.h5"
            parts = d.filepath.split("/")
            if len(parts) >= 2:
                by_district.setdefault(parts[1], []).append(d)
        elif "cps" in d.name.lower():
            national.append(d)

    return national, by_state, by_district


def _get_datasets_for_us_region(
    pe_region,
    national_datasets: list[Dataset],
    state_datasets: dict[str, list[Dataset]],
    district_datasets: dict[str, list[Dataset]],
) -> list[Dataset]:
    """Determine which datasets a US region should link to."""
    if pe_region.region_type == "national":
        return national_datasets

    elif pe_region.region_type == "state":
        # "state/ca" -> "CA"
        state_code = pe_region.code.split("/")[1].upper()
        return state_datasets.get(state_code, national_datasets)

    elif pe_region.region_type == "congressional_district":
        # "congressional_district/CA-12" -> "CA-12"
        district_code = pe_region.code.split("/")[1].upper()
        return district_datasets.get(district_code, national_datasets)

    elif pe_region.region_type == "place":
        # Places use parent state's datasets (filter at runtime)
        if pe_region.state_code:
            return state_datasets.get(pe_region.state_code, national_datasets)
        return national_datasets

    return national_datasets


def _link_datasets(
    region_id,
    datasets: list[Dataset],
    existing_link_set: set[tuple],
    session: Session,
) -> int:
    """Create RegionDatasetLink entries for missing links.

    Returns the number of new links created.
    """
    created = 0
    for dataset in datasets:
        key = (region_id, dataset.id)
        if key not in existing_link_set:
            session.add(RegionDatasetLink(region_id=region_id, dataset_id=dataset.id))
            existing_link_set.add(key)
            created += 1
    return created


def seed_us_regions(
    session: Session,
    skip_places: bool = False,
    skip_districts: bool = False,
) -> tuple[int, int, int]:
    """Seed US regions from policyengine.py registry.

    Args:
        session: Database session
        skip_places: Skip US places (cities over 100K population)
        skip_districts: Skip congressional districts

    Returns:
        Tuple of (created_count, skipped_count, links_created)
    """
    from policyengine.countries.us.regions import us_region_registry

    # Get US model
    us_model = session.exec(
        select(TaxBenefitModel).where(TaxBenefitModel.name == "policyengine-us")
    ).first()

    if not us_model:
        console.print("[red]Error: US model not found. Run seed.py first.[/red]")
        return 0, 0, 0

    # Pre-fetch and group all US datasets
    national_datasets, state_datasets, district_datasets = _group_us_datasets(
        session, us_model.id
    )

    if not national_datasets:
        console.print("[red]Error: No US CPS datasets found. Run seed.py first.[/red]")
        return 0, 0, 0

    # Pre-fetch existing dataset links for efficiency
    existing_links = session.exec(select(RegionDatasetLink)).all()
    existing_link_set = {(link.region_id, link.dataset_id) for link in existing_links}

    created = 0
    skipped = 0
    links_created = 0

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

            # Find existing or create new region
            existing = session.exec(
                select(Region).where(Region.code == pe_region.code)
            ).first()

            if existing:
                db_region = existing
                skipped += 1
            else:
                db_region = Region(
                    code=pe_region.code,
                    label=pe_region.label,
                    region_type=RegionType(pe_region.region_type),
                    requires_filter=pe_region.requires_filter,
                    filter_field=pe_region.filter_field,
                    filter_value=pe_region.filter_value,
                    filter_strategy=(
                        pe_region.scoping_strategy.strategy_type
                        if pe_region.scoping_strategy
                        else None
                    ),
                    parent_code=pe_region.parent_code,
                    state_code=pe_region.state_code,
                    state_name=pe_region.state_name,
                    tax_benefit_model_id=us_model.id,
                )
                session.add(db_region)
                session.flush()  # Get the ID assigned
                created += 1

            # Link datasets for this region
            datasets = _get_datasets_for_us_region(
                pe_region, national_datasets, state_datasets, district_datasets
            )
            links_created += _link_datasets(
                db_region.id, datasets, existing_link_set, session
            )

            progress.advance(task)

        session.commit()

    return created, skipped, links_created


def seed_uk_regions(session: Session) -> tuple[int, int, int]:
    """Seed UK regions from policyengine.py registry.

    Args:
        session: Database session

    Returns:
        Tuple of (created_count, skipped_count, links_created)
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
        return 0, 0, 0

    # Get all UK FRS datasets
    uk_datasets = session.exec(
        select(Dataset)
        .where(Dataset.tax_benefit_model_id == uk_model.id)
        .where(Dataset.name.contains("frs"))  # type: ignore
    ).all()

    if not uk_datasets:
        console.print(
            "[yellow]Warning: No UK FRS datasets found. Skipping UK regions.[/yellow]"
        )
        return 0, 0, 0

    # Pre-fetch existing dataset links
    existing_links = session.exec(select(RegionDatasetLink)).all()
    existing_link_set = {(link.region_id, link.dataset_id) for link in existing_links}

    created = 0
    skipped = 0
    links_created = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("UK regions", total=len(uk_region_registry.regions))

        for pe_region in uk_region_registry.regions:
            progress.update(task, description=f"UK: {pe_region.label}")

            # Find existing or create new region
            existing = session.exec(
                select(Region).where(Region.code == pe_region.code)
            ).first()

            if existing:
                db_region = existing
                skipped += 1
            else:
                db_region = Region(
                    code=pe_region.code,
                    label=pe_region.label,
                    region_type=RegionType(pe_region.region_type),
                    requires_filter=pe_region.requires_filter,
                    filter_field=pe_region.filter_field,
                    filter_value=pe_region.filter_value,
                    filter_strategy=(
                        pe_region.scoping_strategy.strategy_type
                        if pe_region.scoping_strategy
                        else None
                    ),
                    parent_code=pe_region.parent_code,
                    state_code=None,
                    state_name=None,
                    tax_benefit_model_id=uk_model.id,
                )
                session.add(db_region)
                session.flush()
                created += 1

            # All UK regions link to FRS datasets (they filter at runtime)
            links_created += _link_datasets(
                db_region.id, uk_datasets, existing_link_set, session
            )

            progress.advance(task)

        session.commit()

    return created, skipped, links_created


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
    total_links = 0

    with get_session() as session:
        # Seed US regions
        if not args.uk_only:
            console.print("[bold]US Regions[/bold]")
            us_created, us_skipped, us_links = seed_us_regions(
                session,
                skip_places=args.skip_places,
                skip_districts=args.skip_districts,
            )
            total_created += us_created
            total_skipped += us_skipped
            total_links += us_links
            console.print(
                f"[green]\u2713[/green] US regions: {us_created} created, "
                f"{us_skipped} skipped, {us_links} dataset links added\n"
            )

        # Seed UK regions
        if not args.us_only:
            console.print("[bold]UK Regions[/bold]")
            uk_created, uk_skipped, uk_links = seed_uk_regions(session)
            total_created += uk_created
            total_skipped += uk_skipped
            total_links += uk_links
            console.print(
                f"[green]\u2713[/green] UK regions: {uk_created} created, "
                f"{uk_skipped} skipped, {uk_links} dataset links added\n"
            )

    elapsed = time.time() - start
    console.print(
        f"[bold]Total: {total_created} created, {total_skipped} skipped, "
        f"{total_links} dataset links added[/bold]"
    )
    console.print(f"[bold]Time: {elapsed:.1f}s[/bold]")


if __name__ == "__main__":
    main()
