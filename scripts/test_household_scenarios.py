"""Test household calculation scenarios.

Tests:
1. US California household under current law
2. Scotland household under current law
3. US household: current law vs CTC fully refundable reform
"""

import sys
import time
import requests

BASE_URL = "http://127.0.0.1:8000"


def poll_for_completion(report_id: str, max_attempts: int = 60) -> dict:
    """Poll until report is completed or failed."""
    for attempt in range(max_attempts):
        resp = requests.get(f"{BASE_URL}/analysis/household-impact/{report_id}")
        if resp.status_code != 200:
            raise Exception(f"Failed to get report: {resp.status_code} - {resp.text}")

        result = resp.json()
        status = result["status"].upper()

        if status == "COMPLETED":
            return result
        elif status == "FAILED":
            raise Exception(f"Report failed: {result.get('error_message', 'Unknown error')}")

        time.sleep(0.5)

    raise Exception(f"Timed out after {max_attempts} attempts")


def print_household_summary(result: dict, label: str):
    """Print summary of household calculation result."""
    print(f"\n   {label}:")

    baseline = result.get("baseline_result", {})
    reform = result.get("reform_result", {})

    # Get key metrics from person/household
    if "person" in baseline and baseline["person"]:
        person = baseline["person"][0]
        if "household_net_income" in person:
            baseline_income = person["household_net_income"]
            print(f"      Baseline net income: ${baseline_income:,.2f}")

            if reform and "person" in reform and reform["person"]:
                reform_income = reform["person"][0].get("household_net_income", 0)
                print(f"      Reform net income: ${reform_income:,.2f}")
                print(f"      Difference: ${reform_income - baseline_income:,.2f}")

        # Show some tax/benefit info if available
        for key in ["income_tax", "federal_income_tax", "state_income_tax", "ctc", "refundable_ctc"]:
            if key in person:
                print(f"      {key}: ${person[key]:,.2f}")


def test_us_california():
    """Test 1: US California household under current law."""
    print("\n" + "=" * 60)
    print("TEST 1: US California Household - Current Law")
    print("=" * 60)

    # Create California household
    household_data = {
        "tax_benefit_model_name": "policyengine_us",
        "year": 2024,
        "label": "California test household",
        "people": [
            {"age": 35, "employment_income": 75000},
            {"age": 33, "employment_income": 45000},
            {"age": 8},  # Child
        ],
        "tax_unit": {},
        "family": {},
        "spm_unit": {},
        "marital_unit": {},
        "household": {"state_code": "CA"},
    }

    print("\n   Creating household...")
    resp = requests.post(f"{BASE_URL}/households/", json=household_data)
    if resp.status_code != 201:
        print(f"   FAILED: {resp.status_code} - {resp.text}")
        return None

    household = resp.json()
    household_id = household["id"]
    print(f"   Household ID: {household_id}")

    # Run analysis under current law (no policy_id)
    print("   Running analysis...")
    resp = requests.post(f"{BASE_URL}/analysis/household-impact", json={
        "household_id": household_id,
        "policy_id": None,
    })

    if resp.status_code != 200:
        print(f"   FAILED: {resp.status_code} - {resp.text}")
        return household_id

    report_id = resp.json()["report_id"]
    print(f"   Report ID: {report_id}")

    # Poll for results
    try:
        result = poll_for_completion(report_id)
        print("   Status: COMPLETED")
        print_household_summary(result, "Results")
    except Exception as e:
        print(f"   FAILED: {e}")

    return household_id


def test_scotland():
    """Test 2: Scotland household under current law."""
    print("\n" + "=" * 60)
    print("TEST 2: Scotland Household - Current Law")
    print("=" * 60)

    # Create Scotland household
    household_data = {
        "tax_benefit_model_name": "policyengine_uk",
        "year": 2024,
        "label": "Scotland test household",
        "people": [
            {"age": 40, "employment_income": 45000},
        ],
        "benunit": {},
        "household": {"region": "SCOTLAND"},
    }

    print("\n   Creating household...")
    resp = requests.post(f"{BASE_URL}/households/", json=household_data)
    if resp.status_code != 201:
        print(f"   FAILED: {resp.status_code} - {resp.text}")
        return None

    household = resp.json()
    household_id = household["id"]
    print(f"   Household ID: {household_id}")

    # Run analysis under current law
    print("   Running analysis...")
    resp = requests.post(f"{BASE_URL}/analysis/household-impact", json={
        "household_id": household_id,
        "policy_id": None,
    })

    if resp.status_code != 200:
        print(f"   FAILED: {resp.status_code} - {resp.text}")
        return household_id

    report_id = resp.json()["report_id"]
    print(f"   Report ID: {report_id}")

    # Poll for results
    try:
        result = poll_for_completion(report_id)
        print("   Status: COMPLETED")
        print_household_summary(result, "Results")
    except Exception as e:
        print(f"   FAILED: {e}")

    return household_id


def test_us_ctc_reform():
    """Test 3: US household - current law vs CTC fully refundable."""
    print("\n" + "=" * 60)
    print("TEST 3: US Household - Current Law vs CTC Fully Refundable")
    print("=" * 60)

    # First, find the CTC refundability parameter
    print("\n   Finding CTC refundability parameter...")
    resp = requests.get(f"{BASE_URL}/parameters", params={"search": "ctc", "limit": 50})
    if resp.status_code != 200:
        print(f"   FAILED to search parameters: {resp.status_code}")
        return None, None

    params = resp.json()
    ctc_param = None
    for p in params:
        # Look for the refundable portion parameter
        if "refundable" in p["name"].lower() and "ctc" in p["name"].lower():
            print(f"   Found: {p['name']} (label: {p.get('label')})")
            ctc_param = p
            break

    if not ctc_param:
        # Try searching for child tax credit parameters
        print("   Searching for child_tax_credit parameters...")
        resp = requests.get(f"{BASE_URL}/parameters", params={"search": "child_tax_credit", "limit": 50})
        params = resp.json()
        for p in params:
            print(f"   - {p['name']}")
            if "refundable" in p["name"].lower():
                ctc_param = p
                break

    if not ctc_param:
        print("   Could not find CTC refundability parameter")
        print("   Continuing with household creation anyway...")

    # Create household with children (needed for CTC)
    household_data = {
        "tax_benefit_model_name": "policyengine_us",
        "year": 2024,
        "label": "CTC test household",
        "people": [
            {"age": 35, "employment_income": 30000},  # Lower income to see CTC effect
            {"age": 33, "employment_income": 0},
            {"age": 5},   # Child 1
            {"age": 3},   # Child 2
        ],
        "tax_unit": {},
        "family": {},
        "spm_unit": {},
        "marital_unit": {},
        "household": {"state_code": "TX"},  # Texas - no state income tax
    }

    print("\n   Creating household...")
    resp = requests.post(f"{BASE_URL}/households/", json=household_data)
    if resp.status_code != 201:
        print(f"   FAILED: {resp.status_code} - {resp.text}")
        return None, None

    household = resp.json()
    household_id = household["id"]
    print(f"   Household ID: {household_id}")

    # Create a policy that makes CTC fully refundable
    policy_id = None
    if ctc_param:
        print("\n   Creating CTC fully refundable policy...")
        policy_data = {
            "name": "CTC Fully Refundable",
            "description": "Makes the Child Tax Credit fully refundable",
        }
        resp = requests.post(f"{BASE_URL}/policies/", json=policy_data)
        if resp.status_code == 201:
            policy = resp.json()
            policy_id = policy["id"]
            print(f"   Policy ID: {policy_id}")

            # Add parameter value to make CTC fully refundable
            # The parameter should set refundable portion to 100% or max amount
            pv_data = {
                "parameter_id": ctc_param["id"],
                "value_json": 1.0,  # 100% refundable
                "start_date": "2024-01-01T00:00:00Z",
                "end_date": None,
                "policy_id": policy_id,
            }
            resp = requests.post(f"{BASE_URL}/parameter-values/", json=pv_data)
            if resp.status_code == 201:
                print("   Added parameter value for full refundability")
            else:
                print(f"   Warning: Failed to add parameter value: {resp.status_code} - {resp.text}")
        else:
            print(f"   Warning: Failed to create policy: {resp.status_code}")

    # Run analysis with reform policy
    print("\n   Running analysis (baseline vs reform)...")
    resp = requests.post(f"{BASE_URL}/analysis/household-impact", json={
        "household_id": household_id,
        "policy_id": policy_id,
    })

    if resp.status_code != 200:
        print(f"   FAILED: {resp.status_code} - {resp.text}")
        return household_id, policy_id

    report_id = resp.json()["report_id"]
    print(f"   Report ID: {report_id}")

    # Poll for results
    try:
        result = poll_for_completion(report_id)
        print("   Status: COMPLETED")
        print_household_summary(result, "Results")
    except Exception as e:
        print(f"   FAILED: {e}")

    return household_id, policy_id


def main():
    print("=" * 60)
    print("HOUSEHOLD CALCULATION SCENARIO TESTS")
    print("=" * 60)

    # Track created resources for cleanup
    households = []
    policies = []

    # Test 1: US California
    hh_id = test_us_california()
    if hh_id:
        households.append(hh_id)

    # Test 2: Scotland
    hh_id = test_scotland()
    if hh_id:
        households.append(hh_id)

    # Test 3: CTC Reform
    hh_id, policy_id = test_us_ctc_reform()
    if hh_id:
        households.append(hh_id)
    if policy_id:
        policies.append(policy_id)

    # Cleanup
    print("\n" + "=" * 60)
    print("CLEANUP")
    print("=" * 60)

    for hh_id in households:
        resp = requests.delete(f"{BASE_URL}/households/{hh_id}")
        if resp.status_code == 204:
            print(f"   Deleted household: {hh_id}")
        else:
            print(f"   Warning: Failed to delete household {hh_id}: {resp.status_code}")

    for policy_id in policies:
        resp = requests.delete(f"{BASE_URL}/policies/{policy_id}")
        if resp.status_code == 204:
            print(f"   Deleted policy: {policy_id}")
        else:
            print(f"   Warning: Failed to delete policy {policy_id}: {resp.status_code}")

    print("\n" + "=" * 60)
    print("TESTS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
