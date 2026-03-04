"""Tests for GET /parameters/ and GET /parameters/{id} endpoints."""

from uuid import uuid4

import pytest

from test_fixtures.fixtures_version_filter import (
    MODEL_NAMES,
    create_parameter,
    create_version,
    us_model,  # noqa: F401
    us_two_versions,  # noqa: F401
    us_version,  # noqa: F401
)

# -----------------------------------------------------------------------------
# GET /parameters/ — basic
# -----------------------------------------------------------------------------


class TestListParameters:
    def test_given_no_params_then_returns_empty_list(self, client):
        """Empty database returns an empty list."""
        response = client.get("/parameters")
        assert response.status_code == 200
        assert response.json() == []

    def test_given_parameters_exist_then_returns_list(
        self, client, session, us_version  # noqa: F811
    ):
        """Returns parameters that exist."""
        create_parameter(session, us_version, "gov.rate", "Rate")
        response = client.get("/parameters")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_given_search_by_name_then_returns_matching(
        self, client, session, us_version  # noqa: F811
    ):
        """Search filter matches parameter name."""
        create_parameter(session, us_version, "gov.tax.rate", "Rate")
        create_parameter(session, us_version, "gov.benefit.amount", "Amount")

        response = client.get("/parameters?search=tax")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "gov.tax.rate"

    def test_given_search_by_label_then_returns_matching(
        self, client, session, us_version  # noqa: F811
    ):
        """Search filter matches parameter label (case-insensitive)."""
        create_parameter(session, us_version, "gov.x", "Basic Rate")
        create_parameter(session, us_version, "gov.y", "Amount")

        response = client.get("/parameters?search=basic")
        data = response.json()
        assert len(data) == 1
        assert data[0]["label"] == "Basic Rate"

    def test_given_search_by_description_then_returns_matching(
        self, client, session, us_version  # noqa: F811
    ):
        """Search filter matches parameter description."""
        create_parameter(
            session, us_version, "gov.x", "X", description="The income tax rate"
        )
        create_parameter(session, us_version, "gov.y", "Y", description="A benefit")

        response = client.get("/parameters?search=income")
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "gov.x"

    def test_given_limit_then_returns_at_most_n(
        self, client, session, us_version  # noqa: F811
    ):
        """Limit caps the number of results."""
        for i in range(5):
            create_parameter(session, us_version, f"gov.p{i}", f"P{i}")

        response = client.get("/parameters?limit=2")
        assert len(response.json()) == 2

    def test_given_skip_then_skips_first_n(
        self, client, session, us_version  # noqa: F811
    ):
        """Skip omits the first N results."""
        for i in range(5):
            create_parameter(session, us_version, f"gov.p{i}", f"P{i}")

        response = client.get("/parameters?skip=3&limit=10")
        assert len(response.json()) == 2

    def test_results_ordered_by_name(
        self, client, session, us_version  # noqa: F811
    ):
        """Parameters come back sorted alphabetically by name."""
        create_parameter(session, us_version, "gov.zzz", "Z")
        create_parameter(session, us_version, "gov.aaa", "A")
        names = [p["name"] for p in client.get("/parameters").json()]
        assert names == ["gov.aaa", "gov.zzz"]


# -----------------------------------------------------------------------------
# GET /parameters/ — version filtering
# -----------------------------------------------------------------------------


class TestListParametersVersionFilter:
    def test_given_model_name_then_returns_only_latest_version(
        self, client, session, us_two_versions  # noqa: F811
    ):
        """Model name resolves to latest version; old-version params excluded."""
        v1, v2 = us_two_versions
        create_parameter(session, v1, "gov.old", "Old")
        create_parameter(session, v2, "gov.new", "New")

        data = client.get(
            f"/parameters?tax_benefit_model_name={MODEL_NAMES['US']}"
        ).json()
        assert len(data) == 1
        assert data[0]["name"] == "gov.new"

    def test_given_explicit_version_id_then_returns_that_version(
        self, client, session, us_two_versions  # noqa: F811
    ):
        """Explicit version_id pins to a specific version."""
        v1, v2 = us_two_versions
        create_parameter(session, v1, "gov.old", "Old")
        create_parameter(session, v2, "gov.new", "New")

        data = client.get(
            f"/parameters?tax_benefit_model_version_id={v1.id}"
        ).json()
        assert len(data) == 1
        assert data[0]["name"] == "gov.old"

    def test_given_both_then_version_id_takes_precedence(
        self, client, session, us_two_versions  # noqa: F811
    ):
        """version_id overrides model_name."""
        v1, v2 = us_two_versions
        create_parameter(session, v1, "gov.old", "Old")
        create_parameter(session, v2, "gov.new", "New")

        data = client.get(
            f"/parameters?tax_benefit_model_name={MODEL_NAMES['US']}"
            f"&tax_benefit_model_version_id={v1.id}"
        ).json()
        assert len(data) == 1
        assert data[0]["name"] == "gov.old"

    def test_given_no_filters_then_returns_all_versions(
        self, client, session, us_two_versions  # noqa: F811
    ):
        """Without model/version filter, params from all versions are returned."""
        v1, v2 = us_two_versions
        create_parameter(session, v1, "gov.old", "Old")
        create_parameter(session, v2, "gov.new", "New")

        data = client.get("/parameters").json()
        assert len(data) == 2

    def test_given_nonexistent_model_name_then_returns_404(self, client):
        """Unknown model name → 404."""
        response = client.get(
            "/parameters?tax_benefit_model_name=nonexistent-model"
        )
        assert response.status_code == 404

    def test_given_search_combined_with_version_filter(
        self, client, session, us_two_versions  # noqa: F811
    ):
        """Search + version filter work together."""
        v1, v2 = us_two_versions
        create_parameter(session, v2, "gov.tax.rate", "Rate")
        create_parameter(session, v2, "gov.benefit.amount", "Amount")

        data = client.get(
            f"/parameters?tax_benefit_model_name={MODEL_NAMES['US']}&search=tax"
        ).json()
        assert len(data) == 1
        assert data[0]["name"] == "gov.tax.rate"


# -----------------------------------------------------------------------------
# GET /parameters/{id}
# -----------------------------------------------------------------------------


class TestGetParameter:
    def test_given_valid_id_then_returns_parameter(
        self, client, session, us_version  # noqa: F811
    ):
        """Returns the full parameter data."""
        param = create_parameter(session, us_version, "gov.rate", "Rate")
        response = client.get(f"/parameters/{param.id}")
        assert response.status_code == 200
        assert response.json()["name"] == "gov.rate"

    def test_given_nonexistent_id_then_returns_404(self, client):
        """Unknown UUID → 404."""
        response = client.get(f"/parameters/{uuid4()}")
        assert response.status_code == 404

    def test_response_shape_matches_parameter_read(
        self, client, session, us_version  # noqa: F811
    ):
        """Response contains all ParameterRead fields."""
        param = create_parameter(session, us_version, "gov.rate", "Rate")
        data = client.get(f"/parameters/{param.id}").json()
        for field in ("id", "name", "label", "created_at", "tax_benefit_model_version_id"):
            assert field in data
