"""Test household impact analysis end-to-end.

This script tests the async household impact analysis workflow:
1. Create a stored household
2. Run household impact analysis (returns immediately with report_id)
3. Poll until completed
4. Verify results

Usage:
    uv run python scripts/test_household_impact.py
"""

import sys
import time

import requests

BASE_URL = "http://127.0.0.1:8000"


def main():
    print("=" * 60)
    print("Testing Household Impact Analysis (Async)")
    print("=" * 60)

    # Step 1: Create a US household
    print("\n1. Creating US household...")
    household_data = {
        "tax_benefit_model_name": "policyengine_us",
        "year": 2024,
        "label": "Test household for impact analysis",
        "people": [
            {
                "age": 35,
                "employment_income": 50000,
            }
        ],
        "tax_unit": {},
        "family": {},
        "spm_unit": {},
        "marital_unit": {},
        "household": {"state_code": "NV"},
    }

    resp = requests.post(f"{BASE_URL}/households/", json=household_data)
    if resp.status_code != 201:
        print(f"   FAILED: {resp.status_code} - {resp.text}")
        sys.exit(1)

    household = resp.json()
    household_id = household["id"]
    print(f"   Created household: {household_id}")

    # Step 2: Run household impact analysis
    print("\n2. Starting household impact analysis...")
    impact_request = {
        "household_id": household_id,
        "policy_id": None,  # Single run under current law
    }

    resp = requests.post(f"{BASE_URL}/analysis/household-impact", json=impact_request)
    if resp.status_code != 200:
        print(f"   FAILED: {resp.status_code} - {resp.text}")
        sys.exit(1)

    result = resp.json()
    report_id = result["report_id"]
    status = result["status"]
    print(f"   Report ID: {report_id}")
    print(f"   Initial status: {status}")

    # Step 3: Poll until completed
    print("\n3. Polling for results...")
    max_attempts = 30
    for attempt in range(max_attempts):
        resp = requests.get(f"{BASE_URL}/analysis/household-impact/{report_id}")
        if resp.status_code != 200:
            print(f"   FAILED: {resp.status_code} - {resp.text}")
            sys.exit(1)

        result = resp.json()
        status = result["status"].upper()  # Normalize to uppercase
        print(f"   Attempt {attempt + 1}: status={status}")

        if status == "COMPLETED":
            break
        elif status == "FAILED":
            print(f"   FAILED: {result.get('error_message', 'Unknown error')}")
            sys.exit(1)

        time.sleep(0.5)
    else:
        print(f"   FAILED: Timed out after {max_attempts} attempts")
        sys.exit(1)

    # Step 4: Verify results
    print("\n4. Verifying results...")
    baseline_result = result.get("baseline_result")
    if not baseline_result:
        print("   FAILED: No baseline result")
        sys.exit(1)

    print(f"   Baseline result keys: {list(baseline_result.keys())}")

    # Check for expected entity types
    expected_entities = ["person", "tax_unit", "spm_unit", "family", "marital_unit", "household"]
    for entity in expected_entities:
        if entity in baseline_result:
            print(f"   ✓ {entity}: {len(baseline_result[entity])} entities")
        else:
            print(f"   ✗ {entity}: missing")

    # Look for net_income in person output
    if "person" in baseline_result and baseline_result["person"]:
        person = baseline_result["person"][0]
        if "household_net_income" in person:
            print(f"   household_net_income: ${person['household_net_income']:,.2f}")
        elif "spm_unit_net_income" in person:
            print(f"   spm_unit_net_income: ${person['spm_unit_net_income']:,.2f}")

    # Step 5: Cleanup - delete household
    print("\n5. Cleaning up...")
    resp = requests.delete(f"{BASE_URL}/households/{household_id}")
    if resp.status_code == 204:
        print(f"   Deleted household: {household_id}")
    else:
        print(f"   Warning: Failed to delete household: {resp.status_code}")

    print("\n" + "=" * 60)
    print("SUCCESS: Household impact analysis working correctly!")
    print("=" * 60)


if __name__ == "__main__":
    main()
