"""Seed US model (variables, parameters, parameter values)."""

import argparse
import time

from seed_common import console, get_session, seed_model


def main():
    parser = argparse.ArgumentParser(description="Seed US model")
    parser.add_argument(
        "--lite",
        action="store_true",
        help="Lite mode: skip state parameters",
    )
    args = parser.parse_args()

    # Import here to avoid slow import at module level
    from policyengine.tax_benefit_models.us import us_latest

    console.print("[bold green]Seeding US model...[/bold green]\n")

    start = time.time()
    with get_session() as session:
        version = seed_model(us_latest, session, lite=args.lite)
        console.print(f"[green]✓[/green] US model seeded: {version.id}")

    elapsed = time.time() - start
    console.print(f"\n[bold]Total time: {elapsed:.1f}s[/bold]")


if __name__ == "__main__":
    main()
