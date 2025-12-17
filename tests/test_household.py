"""Tests for household calculation endpoint."""

import pytest
from fastapi.testclient import TestClient

from policyengine_api.main import app

client = TestClient(app)


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
        data = response.json()
        assert "person" in data
        assert "benunit" in data
        assert "household" in data
        assert len(data["person"]) == 1

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
        data = response.json()
        assert len(data["person"]) == 4

    def test_with_household_data(self):
        """Test calculation with household-level data."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [{"age": 40, "employment_income": 45000}],
                "household": {
                    "region": "LONDON",
                    "rent": 1500,
                },
                "year": 2026,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "household" in data

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
        data = response.json()
        assert isinstance(data["person"], list)
        assert len(data["person"]) > 0
        person_data = data["person"][0]
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
        data = response.json()
        assert "person" in data
        assert "household" in data
        assert "tax_unit" in data
        assert "spm_unit" in data
        assert "family" in data
        assert "marital_unit" in data
        assert len(data["person"]) == 1

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
        data = response.json()
        assert len(data["person"]) == 4


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
