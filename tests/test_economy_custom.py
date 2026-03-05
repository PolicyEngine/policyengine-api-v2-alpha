"""Tests for POST /analysis/economy-custom endpoint."""

from uuid import uuid4

from policyengine_api.api.analysis import (
    EconomicImpactResponse,
    SimulationInfo,
    _build_filtered_response,
)
from policyengine_api.models import ReportStatus, SimulationStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stub_response(**overrides) -> EconomicImpactResponse:
    """Build a minimal EconomicImpactResponse for testing."""
    defaults = dict(
        report_id=uuid4(),
        status=ReportStatus.COMPLETED,
        baseline_simulation=SimulationInfo(
            id=uuid4(), status=SimulationStatus.COMPLETED
        ),
        reform_simulation=SimulationInfo(id=uuid4(), status=SimulationStatus.COMPLETED),
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


# All data fields that can be nullified by module filtering
_DATA_FIELDS = {
    "decile_impacts",
    "program_statistics",
    "poverty",
    "inequality",
    "budget_summary",
    "intra_decile",
    "detailed_budget",
    "congressional_district_impact",
    "constituency_impact",
    "local_authority_impact",
    "wealth_decile",
    "intra_wealth_decile",
}

_ALWAYS_INCLUDED = {
    "report_id",
    "status",
    "baseline_simulation",
    "reform_simulation",
    "region",
    "error_message",
}


# ---------------------------------------------------------------------------
# Unit tests for _build_filtered_response
# ---------------------------------------------------------------------------


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

    def test_region_always_included(self):
        from policyengine_api.api.analysis import RegionInfo

        region = RegionInfo(
            code="uk",
            label="United Kingdom",
            region_type="national",
            requires_filter=False,
        )
        resp = _make_stub_response(region=region)
        filtered = _build_filtered_response(resp, ["decile"])
        assert filtered.region is not None
        assert filtered.region.code == "uk"

    def test_error_message_always_included(self):
        resp = _make_stub_response(error_message="something went wrong")
        filtered = _build_filtered_response(resp, ["decile"])
        assert filtered.error_message == "something went wrong"

    def test_empty_modules_nullifies_all_data_fields(self):
        resp = _make_stub_response()
        filtered = _build_filtered_response(resp, [])
        for field in _DATA_FIELDS:
            assert getattr(filtered, field) is None, f"{field} should be None"
        assert filtered.report_id == resp.report_id

    def test_empty_modules_preserves_always_included(self):
        resp = _make_stub_response()
        filtered = _build_filtered_response(resp, [])
        for field in _ALWAYS_INCLUDED:
            original = getattr(resp, field)
            assert getattr(filtered, field) == original, f"{field} should be preserved"

    def test_wealth_decile_keeps_both_fields(self):
        resp = _make_stub_response()
        filtered = _build_filtered_response(resp, ["wealth_decile"])
        assert filtered.wealth_decile is not None
        assert filtered.intra_wealth_decile is not None
        assert filtered.decile_impacts is None
        assert filtered.intra_decile is None

    def test_intra_decile_keeps_only_intra_decile(self):
        resp = _make_stub_response()
        filtered = _build_filtered_response(resp, ["intra_decile"])
        assert filtered.intra_decile is not None
        assert filtered.decile_impacts is None
        assert filtered.intra_wealth_decile is None

    def test_congressional_district_keeps_only_district_impact(self):
        resp = _make_stub_response()
        filtered = _build_filtered_response(resp, ["congressional_district"])
        assert filtered.congressional_district_impact is not None
        assert filtered.constituency_impact is None
        assert filtered.local_authority_impact is None

    def test_constituency_keeps_only_constituency_impact(self):
        resp = _make_stub_response()
        filtered = _build_filtered_response(resp, ["constituency"])
        assert filtered.constituency_impact is not None
        assert filtered.congressional_district_impact is None
        assert filtered.local_authority_impact is None

    def test_local_authority_keeps_only_la_impact(self):
        resp = _make_stub_response()
        filtered = _build_filtered_response(resp, ["local_authority"])
        assert filtered.local_authority_impact is not None
        assert filtered.constituency_impact is None
        assert filtered.congressional_district_impact is None

    def test_budget_summary_keeps_only_budget(self):
        resp = _make_stub_response()
        filtered = _build_filtered_response(resp, ["budget_summary"])
        assert filtered.budget_summary is not None
        assert filtered.decile_impacts is None
        assert filtered.program_statistics is None

    def test_unknown_module_in_list_is_gracefully_ignored(self):
        resp = _make_stub_response()
        filtered = _build_filtered_response(resp, ["poverty", "nonexistent_module"])
        assert filtered.poverty is not None
        assert filtered.decile_impacts is None

    def test_all_modules_keeps_all_data_fields(self):
        from policyengine_api.api.module_registry import MODULE_REGISTRY

        resp = _make_stub_response()
        all_names = list(MODULE_REGISTRY.keys())
        filtered = _build_filtered_response(resp, all_names)
        for field in _DATA_FIELDS:
            assert getattr(filtered, field) is not None, (
                f"{field} should be preserved when all modules selected"
            )

    def test_returns_economic_impact_response_instance(self):
        resp = _make_stub_response()
        filtered = _build_filtered_response(resp, ["decile"])
        assert isinstance(filtered, EconomicImpactResponse)


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

    def test_multiple_errors_in_module_validation(self, client):
        response = client.post(
            "/analysis/economy-custom",
            json={
                "tax_benefit_model_name": "policyengine_us",
                "region": "us",
                "modules": ["nonexistent", "constituency"],
            },
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "Unknown module" in detail
        assert "not available for country" in detail

    def test_empty_modules_list_passes_validation(self, client):
        response = client.post(
            "/analysis/economy-custom",
            json={
                "tax_benefit_model_name": "policyengine_us",
                "region": "us",
                "modules": [],
            },
        )
        # Empty list passes module validation, so the error should be about
        # dataset/region resolution, not about modules
        assert (
            response.status_code != 422
            or "module" not in response.json().get("detail", "").lower()
        )

    def test_valid_modules_but_missing_region_returns_404(self, client):
        response = client.post(
            "/analysis/economy-custom",
            json={
                "tax_benefit_model_name": "policyengine_us",
                "region": "us",
                "modules": ["decile", "poverty"],
            },
        )
        # Passes validation but region "us" is not in the DB -> 404
        assert response.status_code == 404

    def test_missing_modules_field_returns_422(self, client):
        response = client.post(
            "/analysis/economy-custom",
            json={
                "tax_benefit_model_name": "policyengine_us",
                "region": "us",
            },
        )
        assert response.status_code == 422

    def test_invalid_model_name_returns_422(self, client):
        response = client.post(
            "/analysis/economy-custom",
            json={
                "tax_benefit_model_name": "invalid_model",
                "region": "us",
                "modules": ["decile"],
            },
        )
        assert response.status_code == 422


class TestEconomyCustomPolling:
    """Tests for GET /analysis/economy-custom/{report_id}."""

    def test_not_found(self, client):
        fake_id = uuid4()
        response = client.get(f"/analysis/economy-custom/{fake_id}")
        assert response.status_code == 404

    def test_invalid_uuid_returns_422(self, client):
        response = client.get("/analysis/economy-custom/not-a-uuid")
        assert response.status_code == 422
