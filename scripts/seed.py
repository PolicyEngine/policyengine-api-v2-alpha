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
    testing     - US only, ~100 curated variables/parameters, fast local testing

Usage:
    python scripts/seed.py                       # Full seed (default)
    python scripts/seed.py --preset=lite         # Lite mode for both countries
    python scripts/seed.py --preset=us-lite      # US only, lite mode
    python scripts/seed.py --preset=minimal      # Minimal seed (no policies/regions)
    python scripts/seed.py --preset=testing      # Fast testing preset (~100 vars/params)
"""

import argparse
import time
from dataclasses import dataclass

# Import seed functions from subscripts
from seed_datasets import seed_uk_datasets, seed_us_datasets
from seed_models import seed_uk_model, seed_us_model
from seed_policies import seed_uk_policy, seed_us_policy
from seed_regions import seed_uk_regions, seed_us_regions
from seed_utils import console, get_session


@dataclass
class SeedConfig:
    """Configuration for database seeding."""

    # Countries
    seed_uk: bool = True
    seed_us: bool = True

    # Models
    skip_state_params: bool = False
    variable_whitelist: set[str] | None = None  # None = all variables
    parameter_prefixes: set[str] | None = None  # None = all parameters

    # Datasets
    dataset_year: int | None = None  # None = all years

    # Policies
    seed_policies: bool = True

    # Regions
    seed_regions: bool = True
    skip_places: bool = False
    skip_districts: bool = False


# Curated variable names for the testing preset (~100 US variables)
TESTING_VARIABLES: set[str] = {
    # Person inputs
    "age",
    "employment_income",
    "self_employment_income",
    "pension_income",
    "social_security",
    "unemployment_compensation",
    "dividend_income",
    "interest_income",
    "capital_gains",
    "rental_income",
    "alimony_income",
    "child_support_received",
    "is_tax_unit_dependent",
    "is_disabled",
    "is_blind",
    "is_pregnant",
    "is_ssi_aged",
    "is_ssi_disabled",
    "marital_status",
    "tax_unit_spouse",
    "is_tax_unit_head",
    "military_basic_pay",
    "farm_income",
    "partnership_s_corp_income",
    "taxable_pension_income",
    # Household/geography
    "state_name",
    "state_code",
    "state_fips",
    "household_size",
    "county",
    "in_nyc",
    "is_on_tribal_land",
    "snap_region",
    "medicaid_rating_area",
    "fips",
    # Tax unit
    "adjusted_gross_income",
    "taxable_income",
    "standard_deduction",
    "itemized_deductions",
    "filing_status",
    "tax_unit_size",
    "tax_unit_dependents",
    "tax_unit_is_joint",
    "income_tax",
    "income_tax_before_credits",
    "income_tax_refundable_credits",
    "income_tax_non_refundable_credits",
    "earned_income",
    "agi",
    "tax_unit_earned_income",
    # Federal tax outputs
    "federal_income_tax",
    "federal_income_tax_before_credits",
    "payroll_tax",
    "employee_payroll_tax",
    "self_employment_tax",
    "earned_income_tax_credit",
    "child_tax_credit",
    "additional_child_tax_credit",
    "child_and_dependent_care_credit",
    "american_opportunity_credit",
    "premium_tax_credit",
    "recovery_rebate_credit",
    "ctc_qualifying_children",
    "eitc_eligible",
    "amt_income",
    # Benefits
    "snap",
    "ssi",
    "tanf",
    "wic",
    "school_meal_subsidy",
    "free_school_meals",
    "reduced_price_school_meals",
    "medicaid",
    "chip",
    "housing_subsidy",
    "section_8_income",
    "lifeline",
    "acp",
    "pell_grant",
    "ssi_amount_if_eligible",
    # Aggregate/summary
    "household_net_income",
    "household_income",
    "household_benefits",
    "household_tax",
    "household_market_income",
    "net_income",
    "market_income",
    "spm_unit_net_income",
    "spm_unit_spm_threshold",
    "in_poverty",
    "in_deep_poverty",
    "poverty_gap",
    "deep_poverty_gap",
    "disposable_income",
    "marginal_tax_rate",
}

# Parameter name prefixes for the testing preset (~100 US parameters)
TESTING_PARAMETER_PREFIXES: set[str] = {
    "gov.irs.income.bracket",
    "gov.irs.deductions.standard",
    "gov.irs.credits.ctc",
    "gov.irs.credits.eitc",
    "gov.usda.snap",
    "gov.ssa.ssi",
    "gov.ssa.social_security",
    "gov.irs.payroll",
    "gov.irs.fica",
    "gov.hhs.tanf",
    "gov.irs.income.amt",
    "gov.irs.capital_gains",
    "gov.irs.credits.premium_tax_credit",
    "gov.irs.income.exemption",
    "gov.hhs.medicaid",
    "gov.contrib.ubi_center.basic_income",
}


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
    "testing": SeedConfig(
        seed_uk=False,
        seed_us=True,
        skip_state_params=True,
        dataset_year=2026,
        seed_policies=True,
        seed_regions=True,
        skip_places=True,
        skip_districts=True,
        variable_whitelist=TESTING_VARIABLES,
        parameter_prefixes=TESTING_PARAMETER_PREFIXES,
    ),
}


def run_seed(config: SeedConfig):
    """Run database seeding with the given configuration."""
    start = time.time()

    with get_session() as session:
        # Step 1: Seed models
        console.print("[bold blue]Step 1: Seeding models...[/bold blue]\n")

        if config.seed_uk:
            seed_uk_model(
                session,
                skip_state_params=config.skip_state_params,
                variable_whitelist=config.variable_whitelist,
                parameter_prefixes=config.parameter_prefixes,
            )

        if config.seed_us:
            seed_us_model(
                session,
                skip_state_params=config.skip_state_params,
                variable_whitelist=config.variable_whitelist,
                parameter_prefixes=config.parameter_prefixes,
            )

        # Step 2: Seed datasets
        console.print("[bold blue]Step 2: Seeding datasets...[/bold blue]\n")

        if config.seed_uk:
            console.print("[bold]UK Datasets[/bold]")
            uk_created, uk_skipped = seed_uk_datasets(session, year=config.dataset_year)
            console.print(
                f"[green]✓[/green] UK: {uk_created} created, {uk_skipped} skipped\n"
            )

        if config.seed_us:
            console.print("[bold]US Datasets[/bold]")
            us_created, us_skipped = seed_us_datasets(session, year=config.dataset_year)
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
                us_created, us_skipped, us_links = seed_us_regions(
                    session,
                    skip_places=config.skip_places,
                    skip_districts=config.skip_districts,
                )
                console.print(
                    f"[green]✓[/green] US: {us_created} created, {us_skipped} skipped, {us_links} dataset links\n"
                )

            if config.seed_uk:
                console.print("[bold]UK Regions[/bold]")
                uk_created, uk_skipped, uk_links = seed_uk_regions(session)
                console.print(
                    f"[green]✓[/green] UK: {uk_created} created, {uk_skipped} skipped, {uk_links} dataset links\n"
                )

    elapsed = time.time() - start
    console.print("[bold green]✓ Database seeding complete![/bold green]")
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
  testing     US only, ~100 curated variables/parameters, fast local testing
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

    year_str = f", {config.dataset_year} only" if config.dataset_year else ""  # noqa: F841
    state_str = ", skip state params" if config.skip_state_params else ""  # noqa: F841

    console.print(
        f"[bold green]PolicyEngine database seeding[/bold green] "
        f"[dim](preset: {args.preset})[/dim]\n"
    )
    console.print(f"  Countries: {country_str}")
    console.print(
        f"  Datasets: {'all years' if not config.dataset_year else config.dataset_year}"
    )
    if config.skip_state_params:
        console.print("  State params: skipped")
    if config.variable_whitelist is not None:
        console.print(f"  Variables: {len(config.variable_whitelist)} whitelisted")
    if config.parameter_prefixes is not None:
        console.print(f"  Parameter prefixes: {len(config.parameter_prefixes)} active")
    console.print(f"  Policies: {'yes' if config.seed_policies else 'no'}")
    if config.seed_regions:
        region_details = []
        if config.skip_places:
            region_details.append("no places")
        if config.skip_districts:
            region_details.append("no districts")
        region_str = (
            f"yes ({', '.join(region_details)})" if region_details else "yes (all)"
        )
        console.print(f"  Regions: {region_str}")
    else:
        console.print("  Regions: no")
    console.print()

    run_seed(config)


if __name__ == "__main__":
    main()
