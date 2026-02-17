"""Seed PolicyEngine database with models, datasets, policies, and regions.

This is the main orchestrator script that calls individual seed scripts
based on the selected preset.

Presets:
    full        - Everything (default)
    lite        - Both countries, 2026 datasets only, skip state params, core regions
    minimal     - Both countries, 2026 datasets only, skip state params, no policies/regions
    uk-lite     - UK only, 2026 datasets, skip state params
    uk-minimal  - UK only, 2026 datasets, skip state params, no policies/regions
    us-lite     - US only, 2026 datasets, skip state params, core regions only
    us-minimal  - US only, 2026 datasets, skip state params, no policies/regions

Usage:
    python scripts/seed.py                    # Full seed (default)
    python scripts/seed.py --preset=lite      # Lite mode for both countries
    python scripts/seed.py --preset=us-lite   # US only, lite mode
    python scripts/seed.py --preset=minimal   # Minimal seed (no policies/regions)
"""

import argparse
import time
from dataclasses import dataclass

from seed_utils import console, get_session

# Import seed functions from subscripts
from seed_datasets import seed_uk_datasets, seed_us_datasets
from seed_models import seed_uk_model, seed_us_model
from seed_policies import seed_uk_policy, seed_us_policy
from seed_regions import seed_uk_regions, seed_us_regions


@dataclass
class SeedConfig:
    """Configuration for database seeding."""

    # Countries
    seed_uk: bool = True
    seed_us: bool = True

    # Models
    skip_state_params: bool = False

    # Datasets
    dataset_year: int | None = None  # None = all years

    # Policies
    seed_policies: bool = True

    # Regions
    seed_regions: bool = True
    skip_places: bool = False
    skip_districts: bool = False


# Preset configurations
PRESETS: dict[str, SeedConfig] = {
    "full": SeedConfig(
        seed_uk=True,
        seed_us=True,
        skip_state_params=False,
        dataset_year=None,
        seed_policies=True,
        seed_regions=True,
        skip_places=False,
        skip_districts=False,
    ),
    "lite": SeedConfig(
        seed_uk=True,
        seed_us=True,
        skip_state_params=True,
        dataset_year=2026,
        seed_policies=True,
        seed_regions=True,
        skip_places=True,
        skip_districts=True,
    ),
    "minimal": SeedConfig(
        seed_uk=True,
        seed_us=True,
        skip_state_params=True,
        dataset_year=2026,
        seed_policies=False,
        seed_regions=False,
    ),
    "uk-lite": SeedConfig(
        seed_uk=True,
        seed_us=False,
        skip_state_params=True,
        dataset_year=2026,
        seed_policies=True,
        seed_regions=True,
    ),
    "uk-minimal": SeedConfig(
        seed_uk=True,
        seed_us=False,
        skip_state_params=True,
        dataset_year=2026,
        seed_policies=False,
        seed_regions=False,
    ),
    "us-lite": SeedConfig(
        seed_uk=False,
        seed_us=True,
        skip_state_params=True,
        dataset_year=2026,
        seed_policies=True,
        seed_regions=True,
        skip_places=True,
        skip_districts=True,
    ),
    "us-minimal": SeedConfig(
        seed_uk=False,
        seed_us=True,
        skip_state_params=True,
        dataset_year=2026,
        seed_policies=False,
        seed_regions=False,
    ),
}


def run_seed(config: SeedConfig):
    """Run database seeding with the given configuration."""
    start = time.time()

    with get_session() as session:
        # Step 1: Seed models
        console.print("[bold blue]Step 1: Seeding models...[/bold blue]\n")

        if config.seed_uk:
            seed_uk_model(session, skip_state_params=config.skip_state_params)

        if config.seed_us:
            seed_us_model(session, skip_state_params=config.skip_state_params)

        # Step 2: Seed datasets
        console.print("[bold blue]Step 2: Seeding datasets...[/bold blue]\n")

        if config.seed_uk:
            console.print("[bold]UK Datasets[/bold]")
            uk_created, uk_skipped = seed_uk_datasets(
                session, year=config.dataset_year
            )
            console.print(
                f"[green]✓[/green] UK: {uk_created} created, {uk_skipped} skipped\n"
            )

        if config.seed_us:
            console.print("[bold]US Datasets[/bold]")
            us_created, us_skipped = seed_us_datasets(
                session, year=config.dataset_year
            )
            console.print(
                f"[green]✓[/green] US: {us_created} created, {us_skipped} skipped\n"
            )

        # Step 3: Seed policies
        if config.seed_policies:
            console.print("[bold blue]Step 3: Seeding policies...[/bold blue]\n")

            if config.seed_uk:
                seed_uk_policy(session)

            if config.seed_us:
                seed_us_policy(session)

            console.print()

        # Step 4: Seed regions
        if config.seed_regions:
            console.print("[bold blue]Step 4: Seeding regions...[/bold blue]\n")

            if config.seed_us:
                console.print("[bold]US Regions[/bold]")
                us_created, us_skipped = seed_us_regions(
                    session,
                    skip_places=config.skip_places,
                    skip_districts=config.skip_districts,
                )
                console.print(
                    f"[green]✓[/green] US: {us_created} created, {us_skipped} skipped\n"
                )

            if config.seed_uk:
                console.print("[bold]UK Regions[/bold]")
                uk_created, uk_skipped = seed_uk_regions(session)
                console.print(
                    f"[green]✓[/green] UK: {uk_created} created, {uk_skipped} skipped\n"
                )

    elapsed = time.time() - start
    console.print(f"[bold green]✓ Database seeding complete![/bold green]")
    console.print(f"[bold]Total time: {elapsed:.1f}s[/bold]")


def main():
    parser = argparse.ArgumentParser(
        description="Seed PolicyEngine database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Presets:
  full        Everything (default)
  lite        Both countries, 2026 datasets only, skip state params, core regions
  minimal     Both countries, 2026 datasets only, skip state params, no policies/regions
  uk-lite     UK only, 2026 datasets, skip state params
  uk-minimal  UK only, 2026 datasets, skip state params, no policies/regions
  us-lite     US only, 2026 datasets, skip state params, core regions only
  us-minimal  US only, 2026 datasets, skip state params, no policies/regions
""",
    )
    parser.add_argument(
        "--preset",
        choices=list(PRESETS.keys()),
        default="full",
        help="Seeding preset (default: full)",
    )
    args = parser.parse_args()

    config = PRESETS[args.preset]

    # Build description of what we're doing
    countries = []
    if config.seed_uk:
        countries.append("UK")
    if config.seed_us:
        countries.append("US")
    country_str = " + ".join(countries)

    year_str = f", {config.dataset_year} only" if config.dataset_year else ""
    state_str = ", skip state params" if config.skip_state_params else ""

    console.print(
        f"[bold green]PolicyEngine database seeding[/bold green] "
        f"[dim](preset: {args.preset})[/dim]\n"
    )
    console.print(f"  Countries: {country_str}")
    console.print(f"  Datasets: {'all years' if not config.dataset_year else config.dataset_year}")
    if config.skip_state_params:
        console.print("  State params: skipped")
    console.print(f"  Policies: {'yes' if config.seed_policies else 'no'}")
    if config.seed_regions:
        region_details = []
        if config.skip_places:
            region_details.append("no places")
        if config.skip_districts:
            region_details.append("no districts")
        region_str = f"yes ({', '.join(region_details)})" if region_details else "yes (all)"
        console.print(f"  Regions: {region_str}")
    else:
        console.print("  Regions: no")
    console.print()

    run_seed(config)


if __name__ == "__main__":
    main()
