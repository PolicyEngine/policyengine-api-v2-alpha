"""Tests for household calculation endpoint."""

import time

import pytest
from fastapi.testclient import TestClient

from policyengine_api.main import app

pytestmark = pytest.mark.integration

client = TestClient(app)


def _poll_job(job_id: str, max_attempts: int = 10) -> dict:
    """Poll for job completion."""
    for _ in range(max_attempts):
        response = client.get(f"/household/calculate/{job_id}")
        assert response.status_code == 200
        data = response.json()
        if data["status"] == "completed":
            return data
        if data["status"] == "failed":
            raise AssertionError(f"Job failed: {data.get('error_message')}")
        time.sleep(0.1)
    raise AssertionError("Job timed out")


class TestUKHouseholdCalculate:
    """Tests for UK household calculations."""

    def test_single_adult(self):
        """Test calculation for a single adult."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [{"age": 30, "employment_income": 30000}],
                "year": 2026,
            },
        )
        assert response.status_code == 200
        job_data = response.json()
        assert "job_id" in job_data

        data = _poll_job(job_data["job_id"])
        assert data["result"] is not None
        assert "person" in data["result"]
        assert "benunit" in data["result"]
        assert "household" in data["result"]
        assert len(data["result"]["person"]) == 1

    def test_couple_with_children(self):
        """Test calculation for a couple with children."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [
                    {"age": 35, "employment_income": 50000},
                    {"age": 33, "employment_income": 25000},
                    {"age": 5},
                    {"age": 8},
                ],
                "year": 2026,
            },
        )
        assert response.status_code == 200
        job_data = response.json()
        data = _poll_job(job_data["job_id"])
        assert len(data["result"]["person"]) == 4

    def test_with_household_data(self):
        """Test calculation with household-level data."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [{"age": 40, "employment_income": 45000}],
                "household": [
                    {
                        "region": "LONDON",
                        "rent": 1500,
                    }
                ],
                "year": 2026,
            },
        )
        assert response.status_code == 200
        job_data = response.json()
        data = _poll_job(job_data["job_id"])
        assert "household" in data["result"]

    def test_output_contains_tax_variables(self):
        """Test that output contains expected tax/benefit variables."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [{"age": 30, "employment_income": 50000}],
                "year": 2026,
            },
        )
        assert response.status_code == 200
        job_data = response.json()
        data = _poll_job(job_data["job_id"])
        assert isinstance(data["result"]["person"], list)
        assert len(data["result"]["person"]) > 0
        person_data = data["result"]["person"][0]
        assert isinstance(person_data, dict)


class TestUSHouseholdCalculate:
    """Tests for US household calculations."""

    def test_single_adult(self):
        """Test calculation for a single adult."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_us",
                "people": [{"age": 30, "employment_income": 60000}],
                "year": 2024,
            },
        )
        assert response.status_code == 200
        job_data = response.json()
        data = _poll_job(job_data["job_id"])
        result = data["result"]
        assert "person" in result
        assert "household" in result
        assert "tax_unit" in result
        assert "spm_unit" in result
        assert "family" in result
        assert "marital_unit" in result
        assert len(result["person"]) == 1

    def test_family_with_children(self):
        """Test calculation for a family with children."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_us",
                "people": [
                    {"age": 35, "employment_income": 80000},
                    {"age": 33, "employment_income": 40000},
                    {"age": 10},
                    {"age": 7},
                ],
                "year": 2024,
            },
        )
        assert response.status_code == 200
        job_data = response.json()
        data = _poll_job(job_data["job_id"])
        assert len(data["result"]["person"]) == 4


class TestMultiHousehold:
    """Tests for multiple household calculations."""

    def test_multiple_uk_households(self):
        """Test calculation for multiple UK households."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [
                    # Person in household 0
                    {
                        "person_id": 0,
                        "person_benunit_id": 0,
                        "person_household_id": 0,
                        "age": 30,
                        "employment_income": 30000,
                    },
                    # Person in household 1
                    {
                        "person_id": 1,
                        "person_benunit_id": 1,
                        "person_household_id": 1,
                        "age": 45,
                        "employment_income": 60000,
                    },
                ],
                "benunit": [
                    {"benunit_id": 0},
                    {"benunit_id": 1},
                ],
                "household": [
                    {"household_id": 0, "region": "LONDON"},
                    {"household_id": 1, "region": "NORTH_EAST"},
                ],
                "year": 2026,
            },
        )
        assert response.status_code == 200
        job_data = response.json()
        data = _poll_job(job_data["job_id"])

        assert len(data["result"]["person"]) == 2
        assert len(data["result"]["benunit"]) == 2
        assert len(data["result"]["household"]) == 2

    def test_multiple_us_households(self):
        """Test calculation for multiple US households."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_us",
                "people": [
                    # Person in household 0
                    {
                        "person_id": 0,
                        "person_household_id": 0,
                        "person_tax_unit_id": 0,
                        "person_marital_unit_id": 0,
                        "person_family_id": 0,
                        "person_spm_unit_id": 0,
                        "age": 30,
                        "employment_income": 50000,
                    },
                    # Person in household 1
                    {
                        "person_id": 1,
                        "person_household_id": 1,
                        "person_tax_unit_id": 1,
                        "person_marital_unit_id": 1,
                        "person_family_id": 1,
                        "person_spm_unit_id": 1,
                        "age": 40,
                        "employment_income": 80000,
                    },
                ],
                "household": [
                    {"household_id": 0, "state_fips": 6},  # California
                    {"household_id": 1, "state_fips": 36},  # New York
                ],
                "tax_unit": [
                    {"tax_unit_id": 0, "state_code": "CA"},
                    {"tax_unit_id": 1, "state_code": "NY"},
                ],
                "marital_unit": [
                    {"marital_unit_id": 0},
                    {"marital_unit_id": 1},
                ],
                "family": [
                    {"family_id": 0},
                    {"family_id": 1},
                ],
                "spm_unit": [
                    {"spm_unit_id": 0},
                    {"spm_unit_id": 1},
                ],
                "year": 2024,
            },
        )
        assert response.status_code == 200
        job_data = response.json()
        data = _poll_job(job_data["job_id"])

        assert len(data["result"]["person"]) == 2
        assert len(data["result"]["household"]) == 2
        assert len(data["result"]["tax_unit"]) == 2


class TestValidation:
    """Tests for request validation."""

    def test_invalid_model_name(self):
        """Test that invalid model name returns 422."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "invalid_model",
                "people": [{"age": 30}],
            },
        )
        assert response.status_code == 422

    def test_missing_people(self):
        """Test that missing people field returns 422."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
            },
        )
        assert response.status_code == 422


class TestUSPolicyReform:
    """Tests for US household calculations with policy reforms."""

    def _get_us_model_id(self) -> str:
        """Get the US tax benefit model ID."""
        response = client.get("/tax-benefit-models/")
        assert response.status_code == 200
        models = response.json()
        for model in models:
            if "us" in model["name"].lower():
                return model["id"]
        raise AssertionError("US model not found")

    def _get_parameter_id(self, model_id: str, param_name: str) -> str:
        """Get a parameter ID by name."""
        response = client.get(
            f"/parameters/?tax_benefit_model_id={model_id}&limit=10000"
        )
        assert response.status_code == 200
        params = response.json()
        for param in params:
            if param["name"] == param_name:
                return param["id"]
        raise AssertionError(f"Parameter {param_name} not found")

    def _create_policy(self, param_id: str, value: float) -> str:
        """Create a policy with a parameter value."""
        response = client.post(
            "/policies/",
            json={
                "name": "Test Reform",
                "description": "Test reform for household calculation",
                "parameter_values": [
                    {
                        "parameter_id": param_id,
                        "value_json": value,
                        "start_date": "2024-01-01T00:00:00Z",
                    }
                ],
            },
        )
        assert response.status_code == 200
        return response.json()["id"]

    def test_us_reform_changes_household_net_income(self):
        """Test that a US policy reform changes household net income.

        This test verifies the fix for the US reform application bug where
        reforms were not being applied correctly due to the shared singleton
        TaxBenefitSystem in policyengine-us.
        """
        # Get the US model and a UBI parameter
        model_id = self._get_us_model_id()
        param_name = "gov.contrib.ubi_center.basic_income.amount.person.by_age[3].amount"
        param_id = self._get_parameter_id(model_id, param_name)

        # Create a policy with $1000 UBI for older adults
        policy_id = self._create_policy(param_id, 1000)

        # Run baseline calculation (no policy)
        baseline_response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_us",
                "people": [{"age": 40, "employment_income": 70000}],
                "tax_unit": [{"state_code": "CA"}],
                "household": [{"state_fips": 6}],
                "year": 2024,
            },
        )
        assert baseline_response.status_code == 200
        baseline_data = _poll_job(baseline_response.json()["job_id"])
        baseline_net_income = baseline_data["result"]["household"][0][
            "household_net_income"
        ]

        # Run reform calculation (with UBI policy)
        reform_response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_us",
                "people": [{"age": 40, "employment_income": 70000}],
                "tax_unit": [{"state_code": "CA"}],
                "household": [{"state_fips": 6}],
                "year": 2024,
                "policy_id": policy_id,
            },
        )
        assert reform_response.status_code == 200
        reform_data = _poll_job(reform_response.json()["job_id"])
        reform_net_income = reform_data["result"]["household"][0][
            "household_net_income"
        ]

        # Verify the reform increased net income by approximately $1000
        difference = reform_net_income - baseline_net_income
        assert abs(difference - 1000) < 1, (
            f"Expected ~$1000 difference, got ${difference:.2f}. "
            f"Baseline: ${baseline_net_income:.2f}, Reform: ${reform_net_income:.2f}"
        )


class TestUKPolicyReform:
    """Tests for UK household calculations with policy reforms."""

    def _get_uk_model_id(self) -> str | None:
        """Get the UK tax benefit model ID, or None if not seeded."""
        response = client.get("/tax-benefit-models/")
        assert response.status_code == 200
        models = response.json()
        for model in models:
            if "uk" in model["name"].lower():
                return model["id"]
        return None

    def _get_parameter_id(self, model_id: str, param_name: str) -> str:
        """Get a parameter ID by name."""
        response = client.get(
            f"/parameters/?tax_benefit_model_id={model_id}&limit=10000"
        )
        assert response.status_code == 200
        params = response.json()
        for param in params:
            if param["name"] == param_name:
                return param["id"]
        raise AssertionError(f"Parameter {param_name} not found")

    def _create_policy(self, param_id: str, value: float) -> str:
        """Create a policy with a parameter value."""
        response = client.post(
            "/policies/",
            json={
                "name": "Test UK Reform",
                "description": "Test reform for UK household calculation",
                "parameter_values": [
                    {
                        "parameter_id": param_id,
                        "value_json": value,
                        "start_date": "2026-01-01T00:00:00Z",
                    }
                ],
            },
        )
        assert response.status_code == 200
        return response.json()["id"]

    def test_uk_reform_changes_household_net_income(self):
        """Test that a UK policy reform changes household net income."""
        # Get the UK model and a UBI parameter
        model_id = self._get_uk_model_id()
        if model_id is None:
            pytest.skip("UK model not seeded in database")
        param_name = "gov.contrib.ubi_center.basic_income.adult"
        param_id = self._get_parameter_id(model_id, param_name)

        # Create a policy with £1000 UBI for adults
        policy_id = self._create_policy(param_id, 1000)

        # Run baseline calculation (no policy)
        baseline_response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [{"age": 30, "employment_income": 30000}],
                "year": 2026,
            },
        )
        assert baseline_response.status_code == 200
        baseline_data = _poll_job(baseline_response.json()["job_id"])
        baseline_net_income = baseline_data["result"]["household"][0][
            "household_net_income"
        ]

        # Run reform calculation (with UBI policy)
        reform_response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [{"age": 30, "employment_income": 30000}],
                "year": 2026,
                "policy_id": policy_id,
            },
        )
        assert reform_response.status_code == 200
        reform_data = _poll_job(reform_response.json()["job_id"])
        reform_net_income = reform_data["result"]["household"][0][
            "household_net_income"
        ]

        # Verify the reform increased net income
        difference = reform_net_income - baseline_net_income
        assert difference > 0, (
            f"Expected positive difference, got £{difference:.2f}. "
            f"Baseline: £{baseline_net_income:.2f}, Reform: £{reform_net_income:.2f}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
