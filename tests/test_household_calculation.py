"""Unit tests for household calculation functions.

These tests verify that the calculation functions work correctly with policy reforms,
without requiring database setup or API calls.
"""

import pytest

from policyengine_api.api.household import _calculate_household_us


class TestUSHouseholdCalculation:
    """Unit tests for US household calculation with policy reforms."""

    @pytest.mark.slow
    def test_baseline_calculation(self):
        """Test basic US household calculation without policy."""
        result = _calculate_household_us(
            people=[{"employment_income": 70000, "age": 40}],
            marital_unit=[],
            family=[],
            spm_unit=[],
            tax_unit=[{"state_code": "CA"}],
            household=[{"state_fips": 6}],
            year=2024,
            policy_data=None,
        )

        assert "person" in result
        assert "household" in result
        assert "tax_unit" in result
        assert len(result["person"]) == 1
        assert result["tax_unit"][0]["income_tax"] > 0

    @pytest.mark.slow
    @pytest.mark.skip(
        reason="Reform application not working with policyengine>=3.2.0 — under investigation"
    )
    def test_reform_changes_net_income(self):
        """Test that a US policy reform changes household net income.

        This test verifies the fix for the US reform application bug where
        reforms were not being applied correctly due to the shared singleton
        TaxBenefitSystem in policyengine-us.

        Uses the federal standard deduction as the reform parameter since
        it is a stable, always-present parameter.
        """
        household_args = {
            "people": [{"employment_income": 70000, "age": 40}],
            "marital_unit": [],
            "family": [],
            "spm_unit": [],
            "tax_unit": [{"state_code": "CA"}],
            "household": [{"state_fips": 6}],
            "year": 2024,
        }

        # Calculate baseline (no policy)
        baseline = _calculate_household_us(**household_args, policy_data=None)
        baseline_net_income = baseline["household"][0]["household_net_income"]

        # Calculate with doubled standard deduction reform
        policy_data = {
            "name": "Test doubled standard deduction",
            "description": "Double the standard deduction",
            "parameter_values": [
                {
                    "parameter_name": "gov.irs.deductions.standard.amount.SINGLE",
                    "value": 29200,
                    "start_date": "2024-01-01T00:00:00",
                    "end_date": None,
                }
            ],
        }
        reform = _calculate_household_us(**household_args, policy_data=policy_data)
        reform_net_income = reform["household"][0]["household_net_income"]

        # Verify the reform changed net income (higher deduction = lower tax = more net income)
        difference = reform_net_income - baseline_net_income
        assert difference > 0, (
            f"Expected positive difference from doubled standard deduction, got ${difference:.2f}. "
            f"Baseline: ${baseline_net_income:.2f}, Reform: ${reform_net_income:.2f}"
        )

    @pytest.mark.slow
    def test_reform_does_not_affect_baseline(self):
        """Test that running reform doesn't pollute baseline calculations.

        This is a regression test for the singleton pollution bug where running
        a reform calculation would affect subsequent baseline calculations.
        """
        household_args = {
            "people": [{"employment_income": 70000, "age": 40}],
            "marital_unit": [],
            "family": [],
            "spm_unit": [],
            "tax_unit": [{"state_code": "CA"}],
            "household": [{"state_fips": 6}],
            "year": 2024,
        }

        # First baseline
        baseline1 = _calculate_household_us(**household_args, policy_data=None)
        baseline1_net_income = baseline1["household"][0]["household_net_income"]

        # Run reform
        policy_data = {
            "name": "Test UBI",
            "description": "Test UBI reform",
            "parameter_values": [
                {
                    "parameter_name": "gov.contrib.ubi_center.basic_income.amount.person.by_age[3].amount",
                    "value": 5000,
                    "start_date": "2024-01-01T00:00:00",
                    "end_date": None,
                }
            ],
        }
        _calculate_household_us(**household_args, policy_data=policy_data)

        # Second baseline - should be same as first
        baseline2 = _calculate_household_us(**household_args, policy_data=None)
        baseline2_net_income = baseline2["household"][0]["household_net_income"]

        # Verify baselines are identical
        assert abs(baseline1_net_income - baseline2_net_income) < 0.01, (
            f"Baseline changed after reform calculation! "
            f"Before: ${baseline1_net_income:.2f}, After: ${baseline2_net_income:.2f}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
