"""Seed example policy reforms for UK and US."""

import time
from datetime import datetime, timezone

import logfire
from sqlmodel import select

from seed_common import console, get_session


def main():
    from policyengine_api.models import (
        Parameter,
        ParameterValue,
        Policy,
        TaxBenefitModel,
        TaxBenefitModelVersion,
    )

    console.print("[bold green]Seeding example policies...[/bold green]\n")

    start = time.time()
    with get_session() as session:
        with logfire.span("seed_example_policies"):
            # Get model versions
            uk_model = session.exec(
                select(TaxBenefitModel).where(TaxBenefitModel.name == "policyengine-uk")
            ).first()
            us_model = session.exec(
                select(TaxBenefitModel).where(TaxBenefitModel.name == "policyengine-us")
            ).first()

            if not uk_model or not us_model:
                console.print(
                    "[red]Error: UK or US model not found. Run seed_*_model.py first.[/red]"
                )
                return

            uk_version = session.exec(
                select(TaxBenefitModelVersion)
                .where(TaxBenefitModelVersion.model_id == uk_model.id)
                .order_by(TaxBenefitModelVersion.created_at.desc())
            ).first()

            us_version = session.exec(
                select(TaxBenefitModelVersion)
                .where(TaxBenefitModelVersion.model_id == us_model.id)
                .order_by(TaxBenefitModelVersion.created_at.desc())
            ).first()

            # UK example policy: raise basic rate to 22p
            uk_policy_name = "UK basic rate 22p"
            existing_uk_policy = session.exec(
                select(Policy).where(Policy.name == uk_policy_name)
            ).first()

            if existing_uk_policy:
                console.print(f"  Policy '{uk_policy_name}' already exists, skipping")
            else:
                # Find the basic rate parameter
                uk_basic_rate_param = session.exec(
                    select(Parameter).where(
                        Parameter.name == "gov.hmrc.income_tax.rates.uk[0].rate",
                        Parameter.tax_benefit_model_version_id == uk_version.id,
                    )
                ).first()

                if uk_basic_rate_param:
                    uk_policy = Policy(
                        name=uk_policy_name,
                        description="Raise the UK income tax basic rate from 20p to 22p",
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
                    console.print(f"  [green]✓[/green] Created UK policy: {uk_policy_name}")
                else:
                    console.print(
                        "  [yellow]Warning: UK basic rate parameter not found[/yellow]"
                    )

            # US example policy: raise first bracket rate to 12%
            us_policy_name = "US 12% lowest bracket"
            existing_us_policy = session.exec(
                select(Policy).where(Policy.name == us_policy_name)
            ).first()

            if existing_us_policy:
                console.print(f"  Policy '{us_policy_name}' already exists, skipping")
            else:
                # Find the first bracket rate parameter
                us_first_bracket_param = session.exec(
                    select(Parameter).where(
                        Parameter.name == "gov.irs.income.bracket.rates.1",
                        Parameter.tax_benefit_model_version_id == us_version.id,
                    )
                ).first()

                if us_first_bracket_param:
                    us_policy = Policy(
                        name=us_policy_name,
                        description="Raise US federal income tax lowest bracket to 12%",
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
                    console.print(f"  [green]✓[/green] Created US policy: {us_policy_name}")
                else:
                    console.print(
                        "  [yellow]Warning: US first bracket parameter not found[/yellow]"
                    )

            console.print("[green]✓[/green] Example policies seeded")

    elapsed = time.time() - start
    console.print(f"\n[bold]Total time: {elapsed:.1f}s[/bold]")


if __name__ == "__main__":
    main()
