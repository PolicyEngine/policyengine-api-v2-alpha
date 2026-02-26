"""Seed example policy reforms.

This script creates example policy reforms for UK and US models.

Usage:
    python scripts/seed_policies.py              # Seed UK and US example policies
    python scripts/seed_policies.py --us-only    # Seed only US example policy
    python scripts/seed_policies.py --uk-only    # Seed only UK example policy
"""

import argparse
from datetime import datetime, timezone

import logfire
from sqlmodel import Session, select

from seed_utils import console, get_session

# Import after seed_utils sets up path
from policyengine_api.models import (  # noqa: E402
    Parameter,
    ParameterValue,
    Policy,
    TaxBenefitModel,
    TaxBenefitModelVersion,
)


def seed_uk_policy(session: Session) -> bool:
    """Seed UK example policy: raise basic rate to 22p.

    Returns:
        True if created, False if skipped
    """
    uk_model = session.exec(
        select(TaxBenefitModel).where(TaxBenefitModel.name == "policyengine-uk")
    ).first()

    if not uk_model:
        console.print("[red]Error: UK model not found. Run seed_models.py first.[/red]")
        return False

    uk_version = session.exec(
        select(TaxBenefitModelVersion)
        .where(TaxBenefitModelVersion.model_id == uk_model.id)
        .order_by(TaxBenefitModelVersion.created_at.desc())
    ).first()

    if not uk_version:
        console.print(
            "[red]Error: UK model version not found. Run seed_models.py first.[/red]"
        )
        return False

    policy_name = "UK basic rate 22p"
    existing = session.exec(select(Policy).where(Policy.name == policy_name)).first()

    if existing:
        console.print(f"  Policy '{policy_name}' already exists, skipping")
        return False

    # Find the basic rate parameter
    uk_basic_rate_param = session.exec(
        select(Parameter).where(
            Parameter.name == "gov.hmrc.income_tax.rates.uk[0].rate",
            Parameter.tax_benefit_model_version_id == uk_version.id,
        )
    ).first()

    if not uk_basic_rate_param:
        console.print("  [yellow]Warning: UK basic rate parameter not found[/yellow]")
        return False

    uk_policy = Policy(
        name=policy_name,
        description="Raise the UK income tax basic rate from 20p to 22p",
        tax_benefit_model_id=uk_model.id,
    )
    session.add(uk_policy)
    session.commit()
    session.refresh(uk_policy)

    # Add parameter value (22% = 0.22)
    uk_param_value = ParameterValue(
        parameter_id=uk_basic_rate_param.id,
        value_json={"value": 0.22},
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=None,
        policy_id=uk_policy.id,
    )
    session.add(uk_param_value)
    session.commit()
    console.print(f"  [green]✓[/green] Created UK policy: {policy_name}")
    return True


def seed_us_policy(session: Session) -> bool:
    """Seed US example policy: raise first bracket to 12%.

    Returns:
        True if created, False if skipped
    """
    us_model = session.exec(
        select(TaxBenefitModel).where(TaxBenefitModel.name == "policyengine-us")
    ).first()

    if not us_model:
        console.print("[red]Error: US model not found. Run seed_models.py first.[/red]")
        return False

    us_version = session.exec(
        select(TaxBenefitModelVersion)
        .where(TaxBenefitModelVersion.model_id == us_model.id)
        .order_by(TaxBenefitModelVersion.created_at.desc())
    ).first()

    if not us_version:
        console.print(
            "[red]Error: US model version not found. Run seed_models.py first.[/red]"
        )
        return False

    policy_name = "US 12% lowest bracket"
    existing = session.exec(select(Policy).where(Policy.name == policy_name)).first()

    if existing:
        console.print(f"  Policy '{policy_name}' already exists, skipping")
        return False

    # Find the first bracket rate parameter
    us_first_bracket_param = session.exec(
        select(Parameter).where(
            Parameter.name == "gov.irs.income.bracket.rates.1",
            Parameter.tax_benefit_model_version_id == us_version.id,
        )
    ).first()

    if not us_first_bracket_param:
        console.print(
            "  [yellow]Warning: US first bracket parameter not found[/yellow]"
        )
        return False

    us_policy = Policy(
        name=policy_name,
        description="Raise US federal income tax lowest bracket to 12%",
        tax_benefit_model_id=us_model.id,
    )
    session.add(us_policy)
    session.commit()
    session.refresh(us_policy)

    # Add parameter value (12% = 0.12)
    us_param_value = ParameterValue(
        parameter_id=us_first_bracket_param.id,
        value_json={"value": 0.12},
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=None,
        policy_id=us_policy.id,
    )
    session.add(us_param_value)
    session.commit()
    console.print(f"  [green]✓[/green] Created US policy: {policy_name}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Seed example policies")
    parser.add_argument(
        "--us-only",
        action="store_true",
        help="Only seed US example policy",
    )
    parser.add_argument(
        "--uk-only",
        action="store_true",
        help="Only seed UK example policy",
    )
    args = parser.parse_args()

    console.print("[bold green]Seeding example policies...[/bold green]\n")

    with get_session() as session:
        if not args.us_only:
            seed_uk_policy(session)

        if not args.uk_only:
            seed_us_policy(session)

    console.print("\n[bold green]✓ Policy seeding complete![/bold green]")


if __name__ == "__main__":
    main()
