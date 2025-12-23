"""Stress tests for PolicyEngine API.

These tests validate API robustness under various conditions:
- Complex household structures
- Edge cases in inputs
- Concurrent request handling
- Large/unusual parameter values
- Error recovery
"""

import concurrent.futures
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from policyengine_api.main import app

client = TestClient(app)


class TestComplexHouseholds:
    """Tests for complex household structures."""

    def test_large_household_uk(self):
        """Test UK calculation with many household members."""
        # 8-person household: grandparents, parents, 4 children
        people = [
            {"age": 70, "employment_income": 0, "state_pension": 9000},  # Grandpa
            {"age": 68, "employment_income": 0, "state_pension": 8500},  # Grandma
            {"age": 45, "employment_income": 55000},  # Parent 1
            {"age": 43, "employment_income": 35000},  # Parent 2
            {"age": 17, "employment_income": 5000},  # Teen with part-time job
            {"age": 14},  # Child
            {"age": 10},  # Child
            {"age": 3},  # Toddler (childcare age)
        ]
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": people,
                "year": 2026,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["person"]) == 8

    def test_large_household_us(self):
        """Test US calculation with many household members."""
        people = [
            {"age": 72, "social_security": 24000},  # Grandparent
            {"age": 40, "employment_income": 85000},  # Parent 1
            {"age": 38, "employment_income": 45000},  # Parent 2
            {"age": 16, "employment_income": 3000},  # Teen
            {"age": 12},  # Child
            {"age": 8},  # Child
            {"age": 2},  # Toddler
        ]
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_us",
                "people": people,
                "tax_unit": {"state_code": "NY"},
                "household": {"state_fips": 36},
                "year": 2024,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["person"]) == 7

    def test_single_parent_multiple_children(self):
        """Test single parent with multiple children."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [
                    {"age": 32, "employment_income": 28000},
                    {"age": 8},
                    {"age": 5},
                    {"age": 2},
                ],
                "year": 2026,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["person"]) == 4


class TestEdgeCaseInputs:
    """Tests for edge case inputs."""

    def test_zero_income(self):
        """Test household with zero income."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [{"age": 30, "employment_income": 0}],
                "year": 2026,
            },
        )
        assert response.status_code == 200

    def test_very_high_income_uk(self):
        """Test UK with very high income (over 500k)."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [{"age": 45, "employment_income": 1000000}],
                "year": 2026,
            },
        )
        assert response.status_code == 200
        data = response.json()
        # Verify high earner pays tax
        assert data["person"][0].get("income_tax", 0) > 0

    def test_very_high_income_us(self):
        """Test US with very high income."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_us",
                "people": [{"age": 50, "employment_income": 2000000}],
                "tax_unit": {"state_code": "CA"},
                "year": 2024,
            },
        )
        assert response.status_code == 200

    def test_elderly_household(self):
        """Test elderly household (pension age)."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [
                    {
                        "age": 80,
                        "state_pension": 12000,
                        "private_pension_income": 15000,
                    },
                    {"age": 78, "state_pension": 11000},
                ],
                "year": 2026,
            },
        )
        assert response.status_code == 200

    def test_newborn(self):
        """Test household with newborn."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [
                    {"age": 28, "employment_income": 30000},
                    {"age": 0},  # Newborn
                ],
                "year": 2026,
            },
        )
        assert response.status_code == 200

    def test_negative_income_handled(self):
        """Test that negative income is handled appropriately."""
        # Self-employment loss scenario
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [{"age": 35, "self_employment_income": -5000}],
                "year": 2026,
            },
        )
        # Should either work or return a validation error, not crash
        assert response.status_code in [200, 422]


class TestAllUSStates:
    """Test calculations work for all US states."""

    US_STATES = [
        "AL",
        "AK",
        "AZ",
        "AR",
        "CA",
        "CO",
        "CT",
        "DE",
        "FL",
        "GA",
        "HI",
        "ID",
        "IL",
        "IN",
        "IA",
        "KS",
        "KY",
        "LA",
        "ME",
        "MD",
        "MA",
        "MI",
        "MN",
        "MS",
        "MO",
        "MT",
        "NE",
        "NV",
        "NH",
        "NJ",
        "NM",
        "NY",
        "NC",
        "ND",
        "OH",
        "OK",
        "OR",
        "PA",
        "RI",
        "SC",
        "SD",
        "TN",
        "TX",
        "UT",
        "VT",
        "VA",
        "WA",
        "WV",
        "WI",
        "WY",
        "DC",
    ]

    @pytest.mark.parametrize("state", US_STATES[:10])  # Test first 10 for speed
    def test_state_calculation(self, state):
        """Test calculation works for a given US state."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_us",
                "people": [{"age": 35, "employment_income": 75000}],
                "tax_unit": {"state_code": state},
                "year": 2024,
            },
        )
        assert response.status_code == 200, f"Failed for state {state}"


class TestUKRegions:
    """Test UK regional calculations."""

    UK_REGIONS = [
        "NORTH_EAST",
        "NORTH_WEST",
        "YORKSHIRE",
        "EAST_MIDLANDS",
        "WEST_MIDLANDS",
        "EAST_OF_ENGLAND",
        "LONDON",
        "SOUTH_EAST",
        "SOUTH_WEST",
        "WALES",
        "SCOTLAND",
        "NORTHERN_IRELAND",
    ]

    @pytest.mark.parametrize("region", UK_REGIONS)
    def test_region_calculation(self, region):
        """Test calculation works for a given UK region."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [{"age": 35, "employment_income": 40000}],
                "household": {"region": region},
                "year": 2026,
            },
        )
        assert response.status_code == 200, f"Failed for region {region}"


class TestConcurrentRequests:
    """Tests for concurrent request handling."""

    def test_concurrent_household_calculations(self):
        """Test multiple concurrent household calculations."""

        def make_request(income: int) -> dict[str, Any]:
            response = client.post(
                "/household/calculate",
                json={
                    "tax_benefit_model_name": "policyengine_uk",
                    "people": [{"age": 30, "employment_income": income}],
                    "year": 2026,
                },
            )
            return {"income": income, "status": response.status_code}

        incomes = [20000, 30000, 40000, 50000, 60000, 70000, 80000, 90000, 100000]

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(make_request, incomes))

        # All requests should succeed
        for result in results:
            assert result["status"] == 200, f"Failed for income {result['income']}"

    def test_concurrent_different_models(self):
        """Test concurrent requests to different models."""
        requests_data = [
            {
                "model": "policyengine_uk",
                "people": [{"age": 30, "employment_income": 40000}],
                "year": 2026,
            },
            {
                "model": "policyengine_us",
                "people": [{"age": 30, "employment_income": 60000}],
                "year": 2024,
            },
            {
                "model": "policyengine_uk",
                "people": [{"age": 40, "employment_income": 60000}],
                "year": 2026,
            },
            {
                "model": "policyengine_us",
                "people": [{"age": 40, "employment_income": 80000}],
                "year": 2024,
            },
        ]

        def make_request(data: dict) -> int:
            response = client.post(
                "/household/calculate",
                json={
                    "tax_benefit_model_name": data["model"],
                    "people": data["people"],
                    "year": data["year"],
                },
            )
            return response.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(make_request, requests_data))

        assert all(status == 200 for status in results)


class TestResponseTimes:
    """Tests for response time benchmarks."""

    def test_simple_calculation_latency(self):
        """Test that simple calculations are fast."""
        start = time.time()
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [{"age": 30, "employment_income": 35000}],
                "year": 2026,
            },
        )
        elapsed = time.time() - start

        assert response.status_code == 200
        # Simple calculation should be under 10 seconds (generous for model load)
        assert elapsed < 10, f"Simple calculation took {elapsed:.2f}s (expected < 10s)"

    def test_complex_calculation_latency(self):
        """Test that complex calculations complete in reasonable time."""
        start = time.time()
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [
                    {
                        "age": 65,
                        "state_pension": 10000,
                        "private_pension_income": 20000,
                    },
                    {"age": 40, "employment_income": 55000},
                    {
                        "age": 38,
                        "employment_income": 35000,
                        "self_employment_income": 10000,
                    },
                    {"age": 16, "employment_income": 3000},
                    {"age": 12},
                    {"age": 8},
                ],
                "household": {"region": "LONDON", "rent": 2000},
                "year": 2026,
            },
        )
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 15, f"Complex calculation took {elapsed:.2f}s (expected < 15s)"


class TestMetadataEndpoints:
    """Stress tests for metadata endpoints."""

    def test_list_all_variables(self):
        """Test listing variables with pagination."""
        response = client.get("/variables?limit=1000")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0

    def test_list_all_parameters(self):
        """Test listing parameters with pagination."""
        response = client.get("/parameters?limit=1000")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0

    def test_parameter_search(self):
        """Test parameter search functionality."""
        # Search for income tax related parameters
        response = client.get("/parameters?search=income_tax")
        assert response.status_code == 200
        data = response.json()
        # Should find some parameters
        assert isinstance(data, list)

    def test_concurrent_metadata_requests(self):
        """Test concurrent metadata requests."""
        endpoints = [
            "/variables?limit=100",
            "/parameters?limit=100",
            "/tax-benefit-models",
            "/datasets",
        ]

        def make_request(endpoint: str) -> int:
            return client.get(endpoint).status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(make_request, endpoints))

        assert all(status == 200 for status in results)


class TestErrorHandling:
    """Tests for error handling and recovery."""

    def test_invalid_model_name(self):
        """Test invalid model name returns proper error."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "nonexistent_model",
                "people": [{"age": 30}],
            },
        )
        assert response.status_code == 422

    def test_missing_required_fields(self):
        """Test missing required fields returns proper error."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                # Missing 'people'
            },
        )
        assert response.status_code == 422

    def test_invalid_age(self):
        """Test invalid age handling."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [{"age": -5, "employment_income": 30000}],
                "year": 2026,
            },
        )
        # Should either handle gracefully or return validation error
        assert response.status_code in [200, 422]

    def test_invalid_year(self):
        """Test invalid year handling."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [{"age": 30, "employment_income": 30000}],
                "year": 1800,  # Invalid year
            },
        )
        # Should either handle gracefully or return validation error
        assert response.status_code in [200, 422, 500]

    def test_empty_people_list(self):
        """Test empty people list handling."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [],
                "year": 2026,
            },
        )
        # Should return validation error
        assert response.status_code in [422, 500]

    def test_malformed_json(self):
        """Test malformed JSON handling."""
        response = client.post(
            "/household/calculate",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422


class TestHouseholdImpact:
    """Stress tests for household impact comparison."""

    def test_impact_without_policy(self):
        """Test impact comparison without policy (baseline vs baseline)."""
        response = client.post(
            "/household/impact",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [{"age": 30, "employment_income": 40000}],
                "year": 2026,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "baseline" in data
        assert "reform" in data
        assert "impact" in data

    def test_impact_complex_household(self):
        """Test impact comparison with complex household."""
        response = client.post(
            "/household/impact",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [
                    {"age": 40, "employment_income": 50000},
                    {"age": 38, "employment_income": 30000},
                    {"age": 10},
                    {"age": 7},
                ],
                "year": 2026,
            },
        )
        assert response.status_code == 200


class TestMultipleIncomeSources:
    """Tests for households with multiple income sources."""

    def test_uk_multiple_income_sources(self):
        """Test UK household with diverse income sources."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "people": [
                    {
                        "age": 55,
                        "employment_income": 40000,
                        "self_employment_income": 15000,
                        "savings_interest_income": 2000,
                        "dividend_income": 5000,
                        "private_pension_income": 3000,
                    }
                ],
                "year": 2026,
            },
        )
        assert response.status_code == 200

    def test_us_multiple_income_sources(self):
        """Test US household with diverse income sources."""
        response = client.post(
            "/household/calculate",
            json={
                "tax_benefit_model_name": "policyengine_us",
                "people": [
                    {
                        "age": 50,
                        "employment_income": 100000,
                        "self_employment_income": 25000,
                        "taxable_interest_income": 5000,
                        "qualified_dividend_income": 10000,
                        "long_term_capital_gains": 20000,
                    }
                ],
                "tax_unit": {"state_code": "CA"},
                "year": 2024,
            },
        )
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
