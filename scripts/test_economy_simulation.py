"""Test economy-wide simulation following the exact flow from modal_app.py.

This script mimics the economy-wide simulation code path as closely as possible
to verify whether policy reforms are being applied correctly.
"""

import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
from microdf import MicroDataFrame

# Import exactly as modal_app.py does
from policyengine.core import Simulation as PESimulation
from policyengine.core.policy import ParameterValue as PEParameterValue
from policyengine.core.policy import Policy as PEPolicy
from policyengine.tax_benefit_models.us import us_latest
from policyengine.tax_benefit_models.us.datasets import PolicyEngineUSDataset, USYearData


def create_test_dataset(year: int) -> PolicyEngineUSDataset:
    """Create a small test dataset similar to what would be loaded from storage.

    Uses the same structure as economy-wide datasets but with just a few households.
    """
    # Create 3 test households with different income levels
    # Each household has 2 adults + 2 children (to test CTC)
    n_households = 3
    n_people = n_households * 4  # 4 people per household

    # Person data
    person_data = {
        "person_id": list(range(n_people)),
        "person_household_id": [i // 4 for i in range(n_people)],
        "person_marital_unit_id": [],
        "person_family_id": [i // 4 for i in range(n_people)],
        "person_spm_unit_id": [i // 4 for i in range(n_people)],
        "person_tax_unit_id": [i // 4 for i in range(n_people)],
        "person_weight": [1000.0] * n_people,  # Weight for population scaling
        "age": [],
        "employment_income": [],
    }

    # Build person details
    marital_unit_counter = 0
    for hh in range(n_households):
        base_income = 10000 + (hh * 20000)  # 10k, 30k, 50k
        # Adult 1
        person_data["age"].append(35)
        person_data["employment_income"].append(base_income)
        person_data["person_marital_unit_id"].append(marital_unit_counter)
        # Adult 2
        person_data["age"].append(33)
        person_data["employment_income"].append(0)
        person_data["person_marital_unit_id"].append(marital_unit_counter)
        marital_unit_counter += 1
        # Child 1
        person_data["age"].append(5)
        person_data["employment_income"].append(0)
        person_data["person_marital_unit_id"].append(marital_unit_counter)
        marital_unit_counter += 1
        # Child 2
        person_data["age"].append(3)
        person_data["employment_income"].append(0)
        person_data["person_marital_unit_id"].append(marital_unit_counter)
        marital_unit_counter += 1

    n_marital_units = marital_unit_counter

    # Entity data
    household_data = {
        "household_id": list(range(n_households)),
        "household_weight": [1000.0] * n_households,
        "state_fips": [48] * n_households,  # Texas
    }

    marital_unit_data = {
        "marital_unit_id": list(range(n_marital_units)),
        "marital_unit_weight": [1000.0] * n_marital_units,
    }

    family_data = {
        "family_id": list(range(n_households)),
        "family_weight": [1000.0] * n_households,
    }

    spm_unit_data = {
        "spm_unit_id": list(range(n_households)),
        "spm_unit_weight": [1000.0] * n_households,
    }

    tax_unit_data = {
        "tax_unit_id": list(range(n_households)),
        "tax_unit_weight": [1000.0] * n_households,
    }

    # Create MicroDataFrames (same as economy datasets)
    person_df = MicroDataFrame(pd.DataFrame(person_data), weights="person_weight")
    household_df = MicroDataFrame(pd.DataFrame(household_data), weights="household_weight")
    marital_unit_df = MicroDataFrame(pd.DataFrame(marital_unit_data), weights="marital_unit_weight")
    family_df = MicroDataFrame(pd.DataFrame(family_data), weights="family_weight")
    spm_unit_df = MicroDataFrame(pd.DataFrame(spm_unit_data), weights="spm_unit_weight")
    tax_unit_df = MicroDataFrame(pd.DataFrame(tax_unit_data), weights="tax_unit_weight")

    # Create dataset file
    tmpdir = tempfile.mkdtemp()
    filepath = str(Path(tmpdir) / "test_economy.h5")

    return PolicyEngineUSDataset(
        name="Test Economy Dataset",
        description="Small test dataset for economy simulation",
        filepath=filepath,
        year=year,
        data=USYearData(
            person=person_df,
            household=household_df,
            marital_unit=marital_unit_df,
            family=family_df,
            spm_unit=spm_unit_df,
            tax_unit=tax_unit_df,
        ),
    )


def create_policy_like_modal_app(model_version) -> PEPolicy:
    """Create a policy exactly like _get_pe_policy_us does in modal_app.py.

    This mimics the exact flow:
    1. Look up parameter by name from model_version.parameters
    2. Create PEParameterValue with the parameter, value, start_date, end_date
    3. Create PEPolicy with the parameter values
    """
    param_lookup = {p.name: p for p in model_version.parameters}

    # This is exactly what _get_pe_policy_us does
    pe_param = param_lookup.get("gov.irs.credits.ctc.refundable.fully_refundable")
    if not pe_param:
        raise ValueError("Parameter not found!")

    pe_pv = PEParameterValue(
        parameter=pe_param,
        value=True,  # Make CTC fully refundable
        start_date=datetime(2024, 1, 1),
        end_date=None,
    )

    return PEPolicy(
        name="CTC Fully Refundable",
        description="Makes CTC fully refundable",
        parameter_values=[pe_pv],
    )


def run_economy_simulation(dataset: PolicyEngineUSDataset, policy: PEPolicy | None, label: str) -> dict:
    """Run an economy simulation exactly like modal_app.py does.

    This follows the exact flow from simulate_economy_us:
    1. Create PESimulation with dataset, model version, policy, dynamic
    2. Call pe_sim.ensure() (which calls run() internally)
    3. Access output via pe_sim.output_dataset
    """
    print(f"\n=== {label} ===")
    print(f"  Policy: {policy.name if policy else 'None (baseline)'}")
    if policy:
        print(f"  Policy parameter_values: {len(policy.parameter_values)}")
        for pv in policy.parameter_values:
            print(f"    - {pv.parameter.name}: {pv.value} (start: {pv.start_date})")

    pe_model_version = us_latest

    # Create and run simulation - EXACTLY like modal_app.py lines 1006-1012
    pe_sim = PESimulation(
        dataset=dataset,
        tax_benefit_model_version=pe_model_version,
        policy=policy,
        dynamic=None,
    )
    pe_sim.ensure()

    # Extract results from output dataset
    output_data = pe_sim.output_dataset.data

    # Sum up key metrics across all tax units (weighted)
    tax_unit_df = pd.DataFrame(output_data.tax_unit)

    # Get the variables we care about
    total_ctc = 0
    total_income_tax = 0
    total_eitc = 0

    for var in ["ctc", "income_tax", "eitc"]:
        if var in tax_unit_df.columns:
            # Weighted sum
            weights = tax_unit_df.get("tax_unit_weight", pd.Series([1.0] * len(tax_unit_df)))
            if var == "ctc":
                total_ctc = (tax_unit_df[var] * weights).sum()
            elif var == "income_tax":
                total_income_tax = (tax_unit_df[var] * weights).sum()
            elif var == "eitc":
                total_eitc = (tax_unit_df[var] * weights).sum()

    print(f"  Results (weighted totals across {len(tax_unit_df)} tax units):")
    print(f"    Total CTC: ${total_ctc:,.0f}")
    print(f"    Total Income Tax: ${total_income_tax:,.0f}")
    print(f"    Total EITC: ${total_eitc:,.0f}")

    # Also show per-household breakdown
    print(f"  Per tax unit breakdown:")
    for i in range(len(tax_unit_df)):
        ctc = tax_unit_df["ctc"].iloc[i] if "ctc" in tax_unit_df.columns else 0
        income_tax = tax_unit_df["income_tax"].iloc[i] if "income_tax" in tax_unit_df.columns else 0
        print(f"    Tax Unit {i}: CTC=${ctc:,.0f}, Income Tax=${income_tax:,.0f}")

    return {
        "total_ctc": total_ctc,
        "total_income_tax": total_income_tax,
        "total_eitc": total_eitc,
        "tax_unit_df": tax_unit_df,
    }


def main():
    print("=" * 60)
    print("ECONOMY-WIDE SIMULATION TEST")
    print("Following the exact code path from modal_app.py")
    print("=" * 60)

    year = 2024

    # Create test dataset (same for both simulations)
    print("\nCreating test dataset...")

    # Run baseline simulation
    baseline_dataset = create_test_dataset(year)
    baseline_results = run_economy_simulation(baseline_dataset, None, "BASELINE (no policy)")

    # Create policy exactly like modal_app.py does
    policy = create_policy_like_modal_app(us_latest)

    # Run reform simulation
    reform_dataset = create_test_dataset(year)
    reform_results = run_economy_simulation(reform_dataset, policy, "REFORM (CTC fully refundable)")

    # Compare results
    print("\n" + "=" * 60)
    print("COMPARISON")
    print("=" * 60)

    ctc_diff = reform_results["total_ctc"] - baseline_results["total_ctc"]
    tax_diff = reform_results["total_income_tax"] - baseline_results["total_income_tax"]

    print(f"\nTotal CTC:")
    print(f"  Baseline: ${baseline_results['total_ctc']:,.0f}")
    print(f"  Reform:   ${reform_results['total_ctc']:,.0f}")
    print(f"  Change:   ${ctc_diff:,.0f}")

    print(f"\nTotal Income Tax:")
    print(f"  Baseline: ${baseline_results['total_income_tax']:,.0f}")
    print(f"  Reform:   ${reform_results['total_income_tax']:,.0f}")
    print(f"  Change:   ${tax_diff:,.0f}")

    # Verdict
    print("\n" + "=" * 60)
    print("VERDICT")
    print("=" * 60)

    if baseline_results["total_income_tax"] == reform_results["total_income_tax"]:
        print("\n❌ BUG CONFIRMED: Results are IDENTICAL!")
        print("   The policy reform is NOT being applied to economy simulations.")
    else:
        print("\n✓ NO BUG: Results differ as expected!")
        print(f"   The fully refundable CTC reform changed income tax by ${tax_diff:,.0f}")


if __name__ == "__main__":
    main()
