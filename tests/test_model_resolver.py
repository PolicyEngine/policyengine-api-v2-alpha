"""Tests for model_resolver service and related fixes."""

from uuid import uuid4

import pytest
from fastapi import HTTPException

from policyengine_api.models import (
    Simulation,
    SimulationStatus,
    SimulationType,
    TaxBenefitModel,
    TaxBenefitModelVersion,
)
from policyengine_api.services.model_resolver import (
    resolve_country_from_simulation,
    resolve_country_model,
    resolve_model_name,
    resolve_version_id,
)

# ---------------------------------------------------------------------------
# resolve_model_name
# ---------------------------------------------------------------------------


class TestResolveModelName:
    def test_us_returns_policyengine_us(self):
        assert resolve_model_name("us") == "policyengine-us"

    def test_uk_returns_policyengine_uk(self):
        assert resolve_model_name("uk") == "policyengine-uk"

    def test_invalid_country_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            resolve_model_name("fr")
        assert exc_info.value.status_code == 400
        assert "Unsupported country_id" in exc_info.value.detail


# ---------------------------------------------------------------------------
# resolve_country_model
# ---------------------------------------------------------------------------


class TestResolveCountryModel:
    def test_returns_model_and_latest_version(self, session):
        model = TaxBenefitModel(name="policyengine-us", description="US")
        session.add(model)
        session.commit()
        session.refresh(model)

        v1 = TaxBenefitModelVersion(model_id=model.id, version="1.0", description="Old")
        session.add(v1)
        session.commit()

        v2 = TaxBenefitModelVersion(model_id=model.id, version="2.0", description="New")
        session.add(v2)
        session.commit()
        session.refresh(v2)

        result_model, result_version = resolve_country_model("us", session)
        assert result_model.id == model.id
        assert result_version.id == v2.id

    def test_missing_model_raises_404(self, session):
        with pytest.raises(HTTPException) as exc_info:
            resolve_country_model("us", session)
        assert exc_info.value.status_code == 404
        assert "Model not found" in exc_info.value.detail

    def test_missing_version_raises_404(self, session):
        model = TaxBenefitModel(name="policyengine-uk", description="UK")
        session.add(model)
        session.commit()

        with pytest.raises(HTTPException) as exc_info:
            resolve_country_model("uk", session)
        assert exc_info.value.status_code == 404
        assert "No version found" in exc_info.value.detail


# ---------------------------------------------------------------------------
# resolve_version_id
# ---------------------------------------------------------------------------


class TestResolveVersionId:
    def test_explicit_version_id_returned(self, session):
        model = TaxBenefitModel(name="policyengine-us", description="US")
        session.add(model)
        session.commit()
        session.refresh(model)

        version = TaxBenefitModelVersion(
            model_id=model.id, version="1.0", description="V1"
        )
        session.add(version)
        session.commit()
        session.refresh(version)

        result = resolve_version_id(None, version.id, session)
        assert result == version.id

    def test_explicit_version_id_not_found_raises_404(self, session):
        with pytest.raises(HTTPException) as exc_info:
            resolve_version_id(None, uuid4(), session)
        assert exc_info.value.status_code == 404

    def test_country_id_returns_latest_version(self, session):
        model = TaxBenefitModel(name="policyengine-us", description="US")
        session.add(model)
        session.commit()
        session.refresh(model)

        version = TaxBenefitModelVersion(
            model_id=model.id, version="1.0", description="V1"
        )
        session.add(version)
        session.commit()
        session.refresh(version)

        result = resolve_version_id("us", None, session)
        assert result == version.id

    def test_neither_returns_none(self, session):
        assert resolve_version_id(None, None, session) is None


# ---------------------------------------------------------------------------
# resolve_country_from_simulation
# ---------------------------------------------------------------------------


class TestResolveCountryFromSimulation:
    def _create_simulation(self, session, model_name="policyengine-us"):
        model = TaxBenefitModel(name=model_name, description="Test")
        session.add(model)
        session.commit()
        session.refresh(model)

        version = TaxBenefitModelVersion(
            model_id=model.id, version="1.0", description="V1"
        )
        session.add(version)
        session.commit()
        session.refresh(version)

        sim = Simulation(
            tax_benefit_model_version_id=version.id,
            status=SimulationStatus.PENDING,
            simulation_type=SimulationType.HOUSEHOLD,
        )
        session.add(sim)
        session.commit()
        session.refresh(sim)
        return sim

    def test_us_simulation_returns_us(self, session):
        sim = self._create_simulation(session, "policyengine-us")
        assert resolve_country_from_simulation(sim, session) == "us"

    def test_uk_simulation_returns_uk(self, session):
        sim = self._create_simulation(session, "policyengine-uk")
        assert resolve_country_from_simulation(sim, session) == "uk"

    def test_new_country_returns_country_id(self, session):
        """Forward-compatible: any policyengine-{country} name works."""
        sim = self._create_simulation(session, "policyengine-fr")
        assert resolve_country_from_simulation(sim, session) == "fr"

    def test_bad_model_name_raises_500(self, session):
        sim = self._create_simulation(session, "some-other-model")
        with pytest.raises(HTTPException) as exc_info:
            resolve_country_from_simulation(sim, session)
        assert exc_info.value.status_code == 500
        assert "Unknown model name" in exc_info.value.detail

    def test_missing_version_raises_500(self, session):
        sim = Simulation(
            tax_benefit_model_version_id=uuid4(),
            status=SimulationStatus.PENDING,
            simulation_type=SimulationType.HOUSEHOLD,
        )
        session.add(sim)
        session.commit()
        session.refresh(sim)

        with pytest.raises(HTTPException) as exc_info:
            resolve_country_from_simulation(sim, session)
        assert exc_info.value.status_code == 500
        assert "Model version not found" in exc_info.value.detail
