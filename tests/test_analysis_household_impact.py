"""Tests for household impact analysis endpoints."""

from datetime import date
from uuid import UUID, uuid4

import pytest

from policyengine_api.api.household_analysis import (
    UK_CONFIG,
    US_CONFIG,
    _ensure_list,
    _extract_value,
    _format_date,
    compute_entity_diff,
    compute_entity_list_diff,
    compute_household_impact,
    compute_variable_diff,
    get_calculator,
    get_country_config,
)
from policyengine_api.models import Report, Simulation, SimulationType
from test_fixtures.fixtures_household_analysis import (
    SAMPLE_UK_BASELINE_RESULT,
    SAMPLE_UK_REFORM_RESULT,
    SAMPLE_US_BASELINE_RESULT,
    SAMPLE_US_REFORM_RESULT,
    create_household_for_analysis,
    create_policy,
    setup_uk_model_and_version,
    setup_us_model_and_version,
)

# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestEnsureList:
    """Tests for _ensure_list helper."""

    def test_none_returns_empty_list(self):
        assert _ensure_list(None) == []

    def test_list_returns_same_list(self):
        input_list = [1, 2, 3]
        assert _ensure_list(input_list) == input_list

    def test_dict_wrapped_in_list(self):
        input_dict = {"key": "value"}
        result = _ensure_list(input_dict)
        assert result == [input_dict]

    def test_empty_list_returns_empty_list(self):
        assert _ensure_list([]) == []


class TestExtractValue:
    """Tests for _extract_value helper."""

    def test_dict_with_value_key(self):
        assert _extract_value({"value": 100}) == 100

    def test_dict_without_value_key(self):
        assert _extract_value({"other": 100}) is None

    def test_non_dict_returns_as_is(self):
        assert _extract_value(100) == 100
        assert _extract_value("string") == "string"
        assert _extract_value([1, 2]) == [1, 2]


class TestFormatDate:
    """Tests for _format_date helper."""

    def test_none_returns_none(self):
        assert _format_date(None) is None

    def test_date_object_formatted(self):
        d = date(2024, 1, 15)
        assert _format_date(d) == "2024-01-15"

    def test_string_returns_string(self):
        assert _format_date("2024-01-15") == "2024-01-15"


class TestComputeVariableDiff:
    """Tests for compute_variable_diff helper."""

    def test_numeric_values_return_diff(self):
        result = compute_variable_diff(100, 150)
        assert result == {"baseline": 100, "reform": 150, "change": 50}

    def test_negative_change(self):
        result = compute_variable_diff(150, 100)
        assert result == {"baseline": 150, "reform": 100, "change": -50}

    def test_float_values(self):
        result = compute_variable_diff(100.5, 200.5)
        assert result == {"baseline": 100.5, "reform": 200.5, "change": 100.0}

    def test_non_numeric_baseline_returns_none(self):
        assert compute_variable_diff("string", 100) is None

    def test_non_numeric_reform_returns_none(self):
        assert compute_variable_diff(100, "string") is None

    def test_both_non_numeric_returns_none(self):
        assert compute_variable_diff("a", "b") is None


class TestComputeEntityDiff:
    """Tests for compute_entity_diff helper."""

    def test_computes_diff_for_numeric_keys(self):
        baseline = {"income": 1000, "tax": 200, "name": "John"}
        reform = {"income": 1000, "tax": 150, "name": "John"}
        result = compute_entity_diff(baseline, reform)

        assert "income" in result
        assert result["income"]["change"] == 0
        assert "tax" in result
        assert result["tax"]["change"] == -50
        assert "name" not in result

    def test_missing_key_in_reform_skipped(self):
        baseline = {"income": 1000, "tax": 200}
        reform = {"income": 1000}
        result = compute_entity_diff(baseline, reform)

        assert "income" in result
        assert "tax" not in result

    def test_empty_entities(self):
        assert compute_entity_diff({}, {}) == {}


class TestComputeEntityListDiff:
    """Tests for compute_entity_list_diff helper."""

    def test_computes_diff_for_each_pair(self):
        baseline_list = [{"income": 100}, {"income": 200}]
        reform_list = [{"income": 120}, {"income": 180}]
        result = compute_entity_list_diff(baseline_list, reform_list)

        assert len(result) == 2
        assert result[0]["income"]["change"] == 20
        assert result[1]["income"]["change"] == -20

    def test_empty_lists(self):
        assert compute_entity_list_diff([], []) == []


class TestComputeHouseholdImpact:
    """Tests for compute_household_impact helper."""

    def test_uk_household_impact(self):
        result = compute_household_impact(
            SAMPLE_UK_BASELINE_RESULT,
            SAMPLE_UK_REFORM_RESULT,
            UK_CONFIG,
        )

        assert "person" in result
        assert "benunit" in result
        assert "household" in result

        # Check person income_tax changed
        person_diff = result["person"][0]
        assert "income_tax" in person_diff
        assert person_diff["income_tax"]["baseline"] == 4500.0
        assert person_diff["income_tax"]["reform"] == 4000.0
        assert person_diff["income_tax"]["change"] == -500.0

    def test_us_household_impact(self):
        result = compute_household_impact(
            SAMPLE_US_BASELINE_RESULT,
            SAMPLE_US_REFORM_RESULT,
            US_CONFIG,
        )

        assert "person" in result
        assert "tax_unit" in result
        assert "spm_unit" in result
        assert "family" in result
        assert "marital_unit" in result
        assert "household" in result

        # Check person income_tax changed
        person_diff = result["person"][0]
        assert person_diff["income_tax"]["change"] == -500.0

    def test_missing_entity_skipped(self):
        baseline = {"person": [{"income": 100}]}
        reform = {"person": [{"income": 120}]}
        result = compute_household_impact(baseline, reform, UK_CONFIG)

        assert "person" in result
        assert "benunit" not in result
        assert "household" not in result


class TestGetCountryConfig:
    """Tests for get_country_config helper."""

    def test_uk_model_returns_uk_config(self):
        config = get_country_config("uk")
        assert config == UK_CONFIG
        assert config.name == "uk"
        assert "benunit" in config.entity_types

    def test_us_model_returns_us_config(self):
        config = get_country_config("us")
        assert config == US_CONFIG
        assert config.name == "us"
        assert "tax_unit" in config.entity_types

    def test_unknown_model_defaults_to_us(self):
        config = get_country_config("unknown_model")
        assert config == US_CONFIG


class TestGetCalculator:
    """Tests for get_calculator helper."""

    def test_uk_model_returns_uk_calculator(self):
        from policyengine_api.api.household_analysis import calculate_uk_household

        calc = get_calculator("uk")
        assert calc == calculate_uk_household

    def test_us_model_returns_us_calculator(self):
        from policyengine_api.api.household_analysis import calculate_us_household

        calc = get_calculator("us")
        assert calc == calculate_us_household

    def test_unknown_model_defaults_to_us(self):
        from policyengine_api.api.household_analysis import calculate_us_household

        calc = get_calculator("unknown_model")
        assert calc == calculate_us_household


# ---------------------------------------------------------------------------
# Validation tests (no database required beyond session fixture)
# ---------------------------------------------------------------------------


class TestHouseholdImpactValidation:
    """Tests for request validation."""

    def test_missing_household_id(self, client):
        """Test that missing household_id returns 422."""
        response = client.post(
            "/analysis/household-impact",
            json={},
        )
        assert response.status_code == 422

    def test_invalid_uuid(self, client):
        """Test that invalid UUID returns 422."""
        response = client.post(
            "/analysis/household-impact",
            json={
                "household_id": "not-a-uuid",
            },
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# 404 tests
# ---------------------------------------------------------------------------


class TestHouseholdImpactNotFound:
    """Tests for 404 responses."""

    def test_household_not_found(self, client, session):
        """Test that non-existent household returns 404."""
        # Need model for the model version lookup
        setup_uk_model_and_version(session)

        response = client.post(
            "/analysis/household-impact",
            json={
                "household_id": str(uuid4()),
            },
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_policy_not_found(self, client, session):
        """Test that non-existent policy returns 404."""
        setup_uk_model_and_version(session)
        household = create_household_for_analysis(session)

        response = client.post(
            "/analysis/household-impact",
            json={
                "household_id": str(household.id),
                "reform_policy_id": str(uuid4()),
            },
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_report_not_found(self, client):
        """Test that GET with non-existent report_id returns 404."""
        response = client.get(f"/analysis/household-impact/{uuid4()}")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Record creation tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestHouseholdImpactRecordCreation:
    """Tests for correct record creation."""

    def test_single_run_creates_one_simulation(self, client, session):
        """Single run (no policy_id) creates one simulation."""
        _, version = setup_uk_model_and_version(session)
        household = create_household_for_analysis(session)

        response = client.post(
            "/analysis/household-impact",
            json={
                "household_id": str(household.id),
            },
        )
        # May fail during calculation since policyengine not available,
        # but should create records
        data = response.json()
        assert "report_id" in data
        assert data["report_type"] == "household_single"
        assert data["baseline_simulation"] is not None
        assert data["reform_simulation"] is None

    def test_comparison_creates_two_simulations(self, client, session):
        """Comparison (with policy_id) creates two simulations."""
        model, version = setup_uk_model_and_version(session)
        household = create_household_for_analysis(session)
        policy = create_policy(session, model.id)

        response = client.post(
            "/analysis/household-impact",
            json={
                "household_id": str(household.id),
                "reform_policy_id": str(policy.id),
            },
        )
        data = response.json()
        assert "report_id" in data
        assert data["report_type"] == "household_comparison"
        assert data["baseline_simulation"] is not None
        assert data["reform_simulation"] is not None

    def test_simulation_type_is_household(self, client, session):
        """Created simulations have simulation_type=HOUSEHOLD."""
        _, version = setup_uk_model_and_version(session)
        household = create_household_for_analysis(session)

        response = client.post(
            "/analysis/household-impact",
            json={
                "household_id": str(household.id),
            },
        )
        data = response.json()

        # Check simulation in database (convert string to UUID for query)
        sim_id = UUID(data["baseline_simulation"]["id"])
        sim = session.get(Simulation, sim_id)
        assert sim is not None
        assert sim.simulation_type == SimulationType.HOUSEHOLD
        assert sim.household_id == household.id
        assert sim.dataset_id is None

    def test_report_links_simulations(self, client, session):
        """Report correctly links baseline and reform simulations."""
        model, version = setup_uk_model_and_version(session)
        household = create_household_for_analysis(session)
        policy = create_policy(session, model.id)

        response = client.post(
            "/analysis/household-impact",
            json={
                "household_id": str(household.id),
                "reform_policy_id": str(policy.id),
            },
        )
        data = response.json()

        # Check report in database (convert string to UUID for query)
        report = session.get(Report, UUID(data["report_id"]))
        assert report is not None
        assert report.baseline_simulation_id == UUID(data["baseline_simulation"]["id"])
        assert report.reform_simulation_id == UUID(data["reform_simulation"]["id"])
        assert report.report_type == "household_comparison"


# ---------------------------------------------------------------------------
# Deduplication tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestHouseholdImpactDeduplication:
    """Tests for simulation/report deduplication."""

    def test_same_request_returns_same_simulation(self, client, session):
        """Same household + same parameters returns same simulation ID."""
        _, version = setup_uk_model_and_version(session)
        household = create_household_for_analysis(session)

        # First request
        response1 = client.post(
            "/analysis/household-impact",
            json={"household_id": str(household.id)},
        )
        data1 = response1.json()

        # Second request with same parameters
        response2 = client.post(
            "/analysis/household-impact",
            json={"household_id": str(household.id)},
        )
        data2 = response2.json()

        # Should return same IDs
        assert data1["report_id"] == data2["report_id"]
        assert data1["baseline_simulation"]["id"] == data2["baseline_simulation"]["id"]

    def test_different_policy_creates_different_simulation(self, client, session):
        """Different policy creates different simulation."""
        model, version = setup_uk_model_and_version(session)
        household = create_household_for_analysis(session)
        policy1 = create_policy(session, model.id, name="Policy 1")
        policy2 = create_policy(session, model.id, name="Policy 2")

        # Request with policy1
        response1 = client.post(
            "/analysis/household-impact",
            json={
                "household_id": str(household.id),
                "reform_policy_id": str(policy1.id),
            },
        )
        data1 = response1.json()

        # Request with policy2
        response2 = client.post(
            "/analysis/household-impact",
            json={
                "household_id": str(household.id),
                "reform_policy_id": str(policy2.id),
            },
        )
        data2 = response2.json()

        # Reports should be different
        assert data1["report_id"] != data2["report_id"]
        # Reform simulations should be different
        assert data1["reform_simulation"]["id"] != data2["reform_simulation"]["id"]
        # Baseline simulations should be the same (same household, no policy)
        assert data1["baseline_simulation"]["id"] == data2["baseline_simulation"]["id"]


# ---------------------------------------------------------------------------
# GET endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestGetHouseholdImpact:
    """Tests for GET /analysis/household-impact/{report_id}."""

    def test_get_returns_report_data(self, client, session):
        """GET returns report with simulation info."""
        _, version = setup_uk_model_and_version(session)
        household = create_household_for_analysis(session)

        # Create report via POST
        post_response = client.post(
            "/analysis/household-impact",
            json={"household_id": str(household.id)},
        )
        report_id = post_response.json()["report_id"]

        # GET the report
        get_response = client.get(f"/analysis/household-impact/{report_id}")
        assert get_response.status_code == 200

        data = get_response.json()
        assert data["report_id"] == report_id
        assert data["report_type"] == "household_single"
        assert data["baseline_simulation"] is not None


# ---------------------------------------------------------------------------
# US household tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestUSHouseholdImpact:
    """Tests specific to US households."""

    def test_us_household_creates_simulation(self, client, session):
        """US household creates simulation with correct model."""
        _, version = setup_us_model_and_version(session)
        household = create_household_for_analysis(session, country_id="us")

        response = client.post(
            "/analysis/household-impact",
            json={"household_id": str(household.id)},
        )
        data = response.json()
        assert "report_id" in data
        assert data["baseline_simulation"] is not None
