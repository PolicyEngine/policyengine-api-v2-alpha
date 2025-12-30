"""Tests for economic impact analysis endpoint.

These tests require a running database with seeded data.
Run with: make integration-test
"""

import pytest

pytestmark = pytest.mark.integration
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from policyengine_api.main import app
from policyengine_api.models import Dataset, Simulation, TaxBenefitModel

client = TestClient(app)


class TestEconomicImpactValidation:
    """Tests for request validation (no database required)."""

    def test_invalid_model_name(self):
        """Test that invalid model name returns 422."""
        response = client.post(
            "/analysis/economic-impact",
            json={
                "tax_benefit_model_name": "invalid_model",
                "dataset_id": "00000000-0000-0000-0000-000000000000",
            },
        )
        assert response.status_code == 422

    def test_missing_dataset_id(self):
        """Test that missing dataset_id returns 422."""
        response = client.post(
            "/analysis/economic-impact",
            json={
                "tax_benefit_model_name": "policyengine_uk",
            },
        )
        assert response.status_code == 422

    def test_invalid_uuid(self):
        """Test that invalid UUID returns 422."""
        response = client.post(
            "/analysis/economic-impact",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "dataset_id": "not-a-uuid",
            },
        )
        assert response.status_code == 422


class TestEconomicImpactNotFound:
    """Tests for 404 responses."""

    def test_dataset_not_found(self):
        """Test that non-existent dataset returns 404."""
        response = client.post(
            "/analysis/economic-impact",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "dataset_id": "00000000-0000-0000-0000-000000000000",
            },
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# Integration tests that require a running database with seeded data
# These are marked with pytest.mark.integration and skipped by default
@pytest.mark.integration
class TestEconomicImpactIntegration:
    """Integration tests for economic impact analysis.

    These tests require:
    1. A running Supabase instance
    2. Seeded database with UK/US models and datasets
    """

    @pytest.fixture
    def uk_dataset_id(self, session: Session):
        """Get a UK dataset ID from the database."""
        uk_model = session.exec(
            select(TaxBenefitModel).where(TaxBenefitModel.name == "uk")
        ).first()
        if not uk_model:
            pytest.skip("UK model not found in database")

        dataset = session.exec(
            select(Dataset).where(Dataset.tax_benefit_model_id == uk_model.id)
        ).first()
        if not dataset:
            pytest.skip("No UK dataset found in database")

        return dataset.id

    def test_uk_economic_impact_baseline_only(self, uk_dataset_id):
        """Test UK economic impact with no reform policy."""
        response = client.post(
            "/analysis/economic-impact",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "dataset_id": str(uk_dataset_id),
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert "baseline_simulation_id" in data
        assert "reform_simulation_id" in data
        assert "decile_impacts" in data
        assert "programme_statistics" in data

        # Should have 10 deciles
        assert len(data["decile_impacts"]) == 10

        # Check decile structure
        for di in data["decile_impacts"]:
            assert "decile" in di
            assert "baseline_mean" in di
            assert "reform_mean" in di
            assert "absolute_change" in di

    def test_simulations_created(self, uk_dataset_id, session: Session):
        """Test that simulations are created in the database."""
        response = client.post(
            "/analysis/economic-impact",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "dataset_id": str(uk_dataset_id),
            },
        )
        assert response.status_code == 200
        data = response.json()

        # Check simulations exist in database
        baseline_sim = session.get(Simulation, data["baseline_simulation_id"])
        assert baseline_sim is not None
        assert baseline_sim.status == "completed"

        reform_sim = session.get(Simulation, data["reform_simulation_id"])
        assert reform_sim is not None
        assert reform_sim.status == "completed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
