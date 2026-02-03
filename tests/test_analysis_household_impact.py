"""Tests for household impact analysis endpoints."""

from uuid import uuid4

import pytest

from test_fixtures.fixtures_analysis import (
    create_household_for_analysis,
    create_policy,
    setup_uk_model_and_version,
    setup_us_model_and_version,
)
from policyengine_api.models import Report, ReportStatus, Simulation, SimulationType


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
                "policy_id": str(uuid4()),
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
        _, version = setup_uk_model_and_version(session)
        household = create_household_for_analysis(session)
        policy = create_policy(session, version.id)

        response = client.post(
            "/analysis/household-impact",
            json={
                "household_id": str(household.id),
                "policy_id": str(policy.id),
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

        # Check simulation in database
        sim_id = data["baseline_simulation"]["id"]
        sim = session.get(Simulation, sim_id)
        assert sim is not None
        assert sim.simulation_type == SimulationType.HOUSEHOLD
        assert sim.household_id == household.id
        assert sim.dataset_id is None

    def test_report_links_simulations(self, client, session):
        """Report correctly links baseline and reform simulations."""
        _, version = setup_uk_model_and_version(session)
        household = create_household_for_analysis(session)
        policy = create_policy(session, version.id)

        response = client.post(
            "/analysis/household-impact",
            json={
                "household_id": str(household.id),
                "policy_id": str(policy.id),
            },
        )
        data = response.json()

        # Check report in database
        report = session.get(Report, data["report_id"])
        assert report is not None
        assert report.baseline_simulation_id == data["baseline_simulation"]["id"]
        assert report.reform_simulation_id == data["reform_simulation"]["id"]
        assert report.report_type == "household_comparison"


# ---------------------------------------------------------------------------
# Deduplication tests
# ---------------------------------------------------------------------------


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
        _, version = setup_uk_model_and_version(session)
        household = create_household_for_analysis(session)
        policy1 = create_policy(session, version.id, name="Policy 1")
        policy2 = create_policy(session, version.id, name="Policy 2")

        # Request with policy1
        response1 = client.post(
            "/analysis/household-impact",
            json={
                "household_id": str(household.id),
                "policy_id": str(policy1.id),
            },
        )
        data1 = response1.json()

        # Request with policy2
        response2 = client.post(
            "/analysis/household-impact",
            json={
                "household_id": str(household.id),
                "policy_id": str(policy2.id),
            },
        )
        data2 = response2.json()

        # Reports should be different
        assert data1["report_id"] != data2["report_id"]
        # Reform simulations should be different
        assert (
            data1["reform_simulation"]["id"] != data2["reform_simulation"]["id"]
        )
        # Baseline simulations should be the same (same household, no policy)
        assert (
            data1["baseline_simulation"]["id"] == data2["baseline_simulation"]["id"]
        )


# ---------------------------------------------------------------------------
# GET endpoint tests
# ---------------------------------------------------------------------------


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


class TestUSHouseholdImpact:
    """Tests specific to US households."""

    def test_us_household_creates_simulation(self, client, session):
        """US household creates simulation with correct model."""
        _, version = setup_us_model_and_version(session)
        household = create_household_for_analysis(
            session, tax_benefit_model_name="policyengine_us"
        )

        response = client.post(
            "/analysis/household-impact",
            json={"household_id": str(household.id)},
        )
        data = response.json()
        assert "report_id" in data
        assert data["baseline_simulation"] is not None
