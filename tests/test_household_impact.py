"""Tests for household impact comparison endpoint."""

import pytest

pytestmark = pytest.mark.integration

from fastapi.testclient import TestClient

from policyengine_api.main import app

client = TestClient(app)


class TestUKHouseholdImpact:
    """Tests for UK household impact comparisons."""

    def test_single_adult_impact(self):
        """Test impact comparison for a single adult (baseline vs baseline)."""
        response = client.post(
            "/household/impact",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [{"age": 30, "employment_income": 30000}],
                "year": 2026,
                # No policy_id means baseline vs baseline
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "baseline" in data
        assert "reform" in data
        assert "impact" in data

        # Baseline and reform should be identical without a policy
        assert data["baseline"]["person"] == data["reform"]["person"]
        assert data["baseline"]["household"] == data["reform"]["household"]

    def test_impact_response_structure(self):
        """Test that impact response has correct structure."""
        response = client.post(
            "/household/impact",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [{"age": 35, "employment_income": 50000}],
                "year": 2026,
            },
        )
        assert response.status_code == 200
        data = response.json()

        # Check baseline structure
        assert "person" in data["baseline"]
        assert "benunit" in data["baseline"]
        assert "household" in data["baseline"]

        # Check reform structure
        assert "person" in data["reform"]
        assert "benunit" in data["reform"]
        assert "household" in data["reform"]

        # Check impact structure
        assert "household" in data["impact"]
        assert "person" in data["impact"]


class TestUSHouseholdImpact:
    """Tests for US household impact comparisons."""

    def test_single_adult_impact(self):
        """Test impact comparison for a single US adult."""
        response = client.post(
            "/household/impact",
            json={
                "tax_benefit_model_name": "policyengine_us",
                "people": [{"age": 30, "employment_income": 60000}],
                "year": 2024,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "baseline" in data
        assert "reform" in data
        assert "impact" in data

    def test_family_impact(self):
        """Test impact comparison for a US family."""
        response = client.post(
            "/household/impact",
            json={
                "tax_benefit_model_name": "policyengine_us",
                "people": [
                    {"age": 35, "employment_income": 80000},
                    {"age": 33, "employment_income": 40000},
                    {"age": 10},
                ],
                "year": 2024,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["baseline"]["person"]) == 3
        assert len(data["reform"]["person"]) == 3
        assert len(data["impact"]["person"]) == 3


class TestHouseholdImpactValidation:
    """Tests for request validation."""

    def test_invalid_model_name(self):
        """Test that invalid model name returns 422."""
        response = client.post(
            "/household/impact",
            json={
                "tax_benefit_model_name": "invalid_model",
                "people": [{"age": 30}],
            },
        )
        assert response.status_code == 422

    def test_missing_people(self):
        """Test that missing people field returns 422."""
        response = client.post(
            "/household/impact",
            json={
                "tax_benefit_model_name": "policyengine_uk",
            },
        )
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
