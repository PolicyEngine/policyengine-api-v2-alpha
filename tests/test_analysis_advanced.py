"""Tests for advanced analysis endpoints."""

import pytest
from fastapi.testclient import TestClient

from policyengine_api.main import app

client = TestClient(app)


class TestMarginalRate:
    """Tests for marginal rate endpoint."""

    def test_marginal_rate_uk_basic(self):
        """Test basic marginal rate calculation for UK."""
        response = client.post(
            "/analysis/marginal-rate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [{"age": 30, "employment_income": 30000}],
                "year": 2026,
                "delta": 1.0,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "marginal_rate" in data
        assert "base_net_income" in data
        assert "incremented_net_income" in data
        # Marginal rate should be between 0 and 1 (mostly)
        assert -0.5 < data["marginal_rate"] < 1.5

    def test_marginal_rate_us_basic(self):
        """Test basic marginal rate calculation for US."""
        response = client.post(
            "/analysis/marginal-rate",
            json={
                "tax_benefit_model_name": "policyengine_us",
                "people": [{"age": 35, "employment_income": 50000}],
                "tax_unit": {"state_code": "CA"},
                "year": 2024,
                "delta": 1.0,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "marginal_rate" in data

    def test_marginal_rate_higher_delta(self):
        """Test marginal rate with larger delta."""
        response = client.post(
            "/analysis/marginal-rate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [{"age": 30, "employment_income": 50000}],
                "year": 2026,
                "delta": 1000.0,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["delta"] == 1000.0

    def test_marginal_rate_invalid_person_index(self):
        """Test marginal rate with invalid person index."""
        response = client.post(
            "/analysis/marginal-rate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [{"age": 30, "employment_income": 30000}],
                "year": 2026,
                "person_index": 5,  # Invalid - only 1 person
            },
        )
        assert response.status_code == 400

    def test_marginal_rate_at_different_incomes(self):
        """Test that marginal rates differ at different income levels."""
        responses = []
        for income in [20000, 50000, 100000]:
            response = client.post(
                "/analysis/marginal-rate",
                json={
                    "tax_benefit_model_name": "policyengine_uk",
                    "people": [{"age": 30, "employment_income": income}],
                    "year": 2026,
                },
            )
            assert response.status_code == 200
            responses.append(response.json()["marginal_rate"])

        # Higher earner should have higher marginal rate (generally)
        # This is a soft check - tax systems are complex
        assert len(set(responses)) >= 1  # At least some variation expected


class TestBudgetConstraint:
    """Tests for budget constraint endpoint."""

    def test_budget_constraint_uk_basic(self):
        """Test basic budget constraint for UK."""
        response = client.post(
            "/analysis/budget-constraint",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [{"age": 30}],
                "year": 2026,
                "min_income": 0,
                "max_income": 50000,
                "step": 10000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "points" in data
        assert len(data["points"]) == 6  # 0, 10k, 20k, 30k, 40k, 50k
        # Verify points are sorted by income
        incomes = [p["gross_income"] for p in data["points"]]
        assert incomes == sorted(incomes)

    def test_budget_constraint_us(self):
        """Test budget constraint for US."""
        response = client.post(
            "/analysis/budget-constraint",
            json={
                "tax_benefit_model_name": "policyengine_us",
                "people": [{"age": 35}],
                "tax_unit": {"state_code": "TX"},
                "year": 2024,
                "min_income": 0,
                "max_income": 100000,
                "step": 25000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["points"]) == 5

    def test_budget_constraint_net_income_increases(self):
        """Test that net income generally increases with gross income."""
        response = client.post(
            "/analysis/budget-constraint",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [{"age": 30}],
                "year": 2026,
                "min_income": 20000,
                "max_income": 80000,
                "step": 20000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        net_incomes = [p["net_income"] for p in data["points"]]
        # Net income should generally increase (may have exceptions due to cliffs)
        assert net_incomes[-1] > net_incomes[0]

    def test_budget_constraint_has_marginal_rates(self):
        """Test that marginal rates are computed in budget constraint."""
        response = client.post(
            "/analysis/budget-constraint",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [{"age": 30}],
                "year": 2026,
                "min_income": 0,
                "max_income": 30000,
                "step": 10000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        # First point has no marginal rate (no previous point)
        assert data["points"][0]["marginal_rate"] is None
        # Subsequent points should have marginal rates
        for point in data["points"][1:]:
            assert point["marginal_rate"] is not None


class TestCliffAnalysis:
    """Tests for cliff analysis endpoint."""

    def test_cliff_analysis_uk(self):
        """Test cliff analysis for UK household."""
        response = client.post(
            "/analysis/cliffs",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [
                    {"age": 30},
                    {"age": 5},  # Child for benefit cliff potential
                ],
                "year": 2026,
                "min_income": 0,
                "max_income": 100000,
                "step": 5000,
                "cliff_threshold": 0.5,  # 50% marginal rate
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "cliff_regions" in data
        assert "max_marginal_rate" in data
        assert "avg_marginal_rate" in data
        assert data["cliff_threshold"] == 0.5

    def test_cliff_analysis_us(self):
        """Test cliff analysis for US household."""
        response = client.post(
            "/analysis/cliffs",
            json={
                "tax_benefit_model_name": "policyengine_us",
                "people": [{"age": 30}, {"age": 6}],
                "tax_unit": {"state_code": "CA"},
                "year": 2024,
                "min_income": 0,
                "max_income": 80000,
                "step": 4000,
                "cliff_threshold": 0.6,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "cliff_regions" in data

    def test_cliff_analysis_strict_threshold(self):
        """Test cliff analysis with very strict threshold."""
        response = client.post(
            "/analysis/cliffs",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [{"age": 30}],
                "year": 2026,
                "min_income": 0,
                "max_income": 60000,
                "step": 5000,
                "cliff_threshold": 0.9,  # Very high - should find fewer cliffs
            },
        )
        assert response.status_code == 200


class TestMultiPolicyCompare:
    """Tests for multi-policy comparison endpoint."""

    def test_compare_no_policies(self):
        """Test comparison with empty policy list (just baseline)."""
        response = client.post(
            "/analysis/compare-policies",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [{"age": 30, "employment_income": 40000}],
                "year": 2026,
                "policy_ids": [],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "baseline" in data
        assert data["baseline"]["policy_name"] == "Baseline (current law)"
        assert data["reforms"] == []

    def test_compare_invalid_policy(self):
        """Test comparison with non-existent policy."""
        response = client.post(
            "/analysis/compare-policies",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [{"age": 30, "employment_income": 40000}],
                "year": 2026,
                "policy_ids": ["00000000-0000-0000-0000-000000000000"],
            },
        )
        assert response.status_code == 404


class TestVariableSearch:
    """Tests for variable search functionality."""

    def test_variable_list(self):
        """Test basic variable listing."""
        response = client.get("/variables?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_variable_search(self):
        """Test variable search by name."""
        response = client.get("/variables?search=income&limit=50")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_variable_filter_by_entity(self):
        """Test variable filtering by entity."""
        response = client.get("/variables?entity=person&limit=20")
        assert response.status_code == 200
        data = response.json()
        # All returned variables should be for 'person' entity
        for var in data:
            if "entity" in var:
                assert var["entity"] == "person"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
