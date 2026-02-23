"""Tests for GET /tax-benefit-models/by-country/{country_id} endpoint."""

from datetime import datetime, timezone, timedelta

import pytest

from policyengine_api.models import TaxBenefitModel, TaxBenefitModelVersion


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _create_model_and_version(session, name, description, version_str, **version_kw):
    """Create a model and a single version, return (model, version)."""
    model = TaxBenefitModel(name=name, description=description)
    session.add(model)
    session.commit()
    session.refresh(model)

    version = TaxBenefitModelVersion(
        model_id=model.id,
        version=version_str,
        description=f"{name} {version_str}",
        **version_kw,
    )
    session.add(version)
    session.commit()
    session.refresh(version)
    return model, version


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestModelByCountry:
    """Tests for the by-country lookup."""

    def test_uk_returns_model_and_version(self, client, session):
        """country_id=uk returns the UK model and its latest version."""
        _create_model_and_version(session, "policyengine-uk", "UK model", "2.51.0")

        response = client.get("/tax-benefit-models/by-country/uk")

        assert response.status_code == 200
        data = response.json()
        assert data["model"]["name"] == "policyengine-uk"
        assert data["latest_version"]["version"] == "2.51.0"

    def test_us_returns_model_and_version(self, client, session):
        """country_id=us returns the US model and its latest version."""
        _create_model_and_version(session, "policyengine-us", "US model", "1.20.0")

        response = client.get("/tax-benefit-models/by-country/us")

        assert response.status_code == 200
        data = response.json()
        assert data["model"]["name"] == "policyengine-us"
        assert data["latest_version"]["version"] == "1.20.0"

    def test_multiple_versions_returns_latest(self, client, session):
        """When multiple versions exist, returns the most recently created."""
        model = TaxBenefitModel(name="policyengine-uk", description="UK")
        session.add(model)
        session.commit()
        session.refresh(model)

        old = TaxBenefitModelVersion(
            model_id=model.id,
            version="2.50.0",
            description="Old",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        new = TaxBenefitModelVersion(
            model_id=model.id,
            version="2.51.0",
            description="New",
            created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        session.add(old)
        session.add(new)
        session.commit()

        response = client.get("/tax-benefit-models/by-country/uk")

        assert response.status_code == 200
        assert response.json()["latest_version"]["version"] == "2.51.0"

    def test_no_model_returns_404(self, client):
        """When the model doesn't exist in the DB, returns 404."""
        response = client.get("/tax-benefit-models/by-country/uk")

        assert response.status_code == 404
        assert "No model found" in response.json()["detail"]

    def test_model_without_versions_returns_404(self, client, session):
        """When the model exists but has no versions, returns 404."""
        model = TaxBenefitModel(name="policyengine-uk", description="UK")
        session.add(model)
        session.commit()

        response = client.get("/tax-benefit-models/by-country/uk")

        assert response.status_code == 404
        assert "No versions found" in response.json()["detail"]

    def test_invalid_country_id_returns_422(self, client):
        """An invalid country_id is rejected by Literal validation."""
        response = client.get("/tax-benefit-models/by-country/fr")

        assert response.status_code == 422

    def test_response_shape(self, client, session):
        """Response contains the expected fields for both model and version."""
        _create_model_and_version(session, "policyengine-uk", "UK model", "2.51.0")

        response = client.get("/tax-benefit-models/by-country/uk")
        data = response.json()

        # Model fields
        model = data["model"]
        assert "id" in model
        assert "name" in model
        assert "description" in model
        assert "created_at" in model

        # Version fields
        version = data["latest_version"]
        assert "id" in version
        assert "version" in version
        assert "model_id" in version
        assert "description" in version
        assert "created_at" in version

    def test_country_isolation(self, client, session):
        """UK endpoint doesn't return US model data and vice versa."""
        _create_model_and_version(session, "policyengine-uk", "UK", "2.51.0")
        _create_model_and_version(session, "policyengine-us", "US", "1.20.0")

        uk_resp = client.get("/tax-benefit-models/by-country/uk")
        us_resp = client.get("/tax-benefit-models/by-country/us")

        assert uk_resp.json()["model"]["name"] == "policyengine-uk"
        assert uk_resp.json()["latest_version"]["version"] == "2.51.0"
        assert us_resp.json()["model"]["name"] == "policyengine-us"
        assert us_resp.json()["latest_version"]["version"] == "1.20.0"
