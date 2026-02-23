"""Tests for POST /analysis/economy-custom endpoint."""

import pytest
from unittest.mock import patch

from policyengine_api.api.analysis import (
    EconomicImpactResponse,
    SimulationInfo,
    _build_filtered_response,
)
from policyengine_api.models import ReportStatus, SimulationStatus


# ---------------------------------------------------------------------------
# Unit tests for _build_filtered_response
# ---------------------------------------------------------------------------


def _make_stub_response(**overrides) -> EconomicImpactResponse:
    """Build a minimal EconomicImpactResponse for testing."""
    from uuid import uuid4

    defaults = dict(
        report_id=uuid4(),
        status=ReportStatus.COMPLETED,
        baseline_simulation=SimulationInfo(
            id=uuid4(), status=SimulationStatus.COMPLETED
        ),
        reform_simulation=SimulationInfo(
            id=uuid4(), status=SimulationStatus.COMPLETED
        ),
        region=None,
        error_message=None,
        decile_impacts=[{"fake": "decile"}],
        program_statistics=[{"fake": "program"}],
        poverty=[{"fake": "poverty"}],
        inequality=[{"fake": "inequality"}],
        budget_summary=[{"fake": "budget"}],
        intra_decile=[{"fake": "intra"}],
        detailed_budget={"prog": {"baseline": 1.0}},
        congressional_district_impact=[{"fake": "district"}],
        constituency_impact=[{"fake": "constituency"}],
        local_authority_impact=[{"fake": "la"}],
        wealth_decile=[{"fake": "wealth"}],
        intra_wealth_decile=[{"fake": "intra_wealth"}],
    )
    defaults.update(overrides)
    return EconomicImpactResponse.model_construct(**defaults)


class TestBuildFilteredResponse:
    """Tests for response filtering by module list."""

    def test_single_module_keeps_only_its_fields(self):
        resp = _make_stub_response()
        filtered = _build_filtered_response(resp, ["poverty"])
        assert filtered.poverty is not None
        assert filtered.decile_impacts is None
        assert filtered.program_statistics is None
        assert filtered.inequality is None

    def test_multiple_modules(self):
        resp = _make_stub_response()
        filtered = _build_filtered_response(resp, ["decile", "inequality"])
        assert filtered.decile_impacts is not None
        assert filtered.inequality is not None
        assert filtered.poverty is None
        assert filtered.congressional_district_impact is None

    def test_program_statistics_includes_detailed_budget(self):
        resp = _make_stub_response()
        filtered = _build_filtered_response(resp, ["program_statistics"])
        assert filtered.program_statistics is not None
        assert filtered.detailed_budget is not None
        assert filtered.decile_impacts is None

    def test_always_included_fields_preserved(self):
        resp = _make_stub_response()
        filtered = _build_filtered_response(resp, ["poverty"])
        assert filtered.report_id == resp.report_id
        assert filtered.status == resp.status
        assert filtered.baseline_simulation is not None
        assert filtered.reform_simulation is not None

    def test_empty_modules_nullifies_all_data_fields(self):
        resp = _make_stub_response()
        filtered = _build_filtered_response(resp, [])
        assert filtered.decile_impacts is None
        assert filtered.poverty is None
        assert filtered.inequality is None
        assert filtered.report_id == resp.report_id


# ---------------------------------------------------------------------------
# Integration tests for the endpoint itself
# ---------------------------------------------------------------------------


class TestEconomyCustomEndpoint:
    """Tests for POST /analysis/economy-custom validation."""

    def test_unknown_module_returns_422(self, client):
        response = client.post(
            "/analysis/economy-custom",
            json={
                "tax_benefit_model_name": "policyengine_us",
                "region": "us",
                "modules": ["nonexistent_module"],
            },
        )
        assert response.status_code == 422
        assert "Unknown module" in response.json()["detail"]

    def test_wrong_country_module_returns_422(self, client):
        response = client.post(
            "/analysis/economy-custom",
            json={
                "tax_benefit_model_name": "policyengine_us",
                "region": "us",
                "modules": ["constituency"],
            },
        )
        assert response.status_code == 422
        assert "not available for country" in response.json()["detail"]

    def test_empty_modules_list_returns_422(self, client):
        """An empty modules list should still be accepted (no validation error)."""
        # This will fail on dataset resolution (404), not module validation
        response = client.post(
            "/analysis/economy-custom",
            json={
                "tax_benefit_model_name": "policyengine_us",
                "region": "us",
                "modules": [],
            },
        )
        # Empty list passes validation, so the error should be about
        # dataset/region resolution, not about modules
        assert response.status_code != 422 or "module" not in response.json().get(
            "detail", ""
        ).lower()


class TestEconomyCustomPolling:
    """Tests for GET /analysis/economy-custom/{report_id}."""

    def test_not_found(self, client):
        from uuid import uuid4

        fake_id = uuid4()
        response = client.get(f"/analysis/economy-custom/{fake_id}")
        assert response.status_code == 404
