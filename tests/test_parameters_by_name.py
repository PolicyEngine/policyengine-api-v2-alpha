"""Tests for POST /parameters/by-name endpoint."""

import pytest

from test_fixtures.fixtures_version_filter import (
    MODEL_NAMES,
    create_parameter,
    uk_model,  # noqa: F401
    uk_version,  # noqa: F401
    us_model,  # noqa: F401
    us_two_versions,  # noqa: F401
    us_version,  # noqa: F401
)


# -----------------------------------------------------------------------------
# Happy-path lookups
# -----------------------------------------------------------------------------


class TestParametersByName:
    def test_given_known_names_then_returns_matching(
        self, client, session, us_version  # noqa: F811
    ):
        """Returns full metadata for each matching name."""
        create_parameter(session, us_version, "gov.tax.rate", "Rate")
        create_parameter(session, us_version, "gov.tax.threshold", "Threshold")

        data = client.post(
            "/parameters/by-name",
            json={
                "names": ["gov.tax.rate", "gov.tax.threshold"],
                "tax_benefit_model_name": MODEL_NAMES["US"],
            },
        ).json()

        assert len(data) == 2
        assert {p["name"] for p in data} == {"gov.tax.rate", "gov.tax.threshold"}

    def test_given_empty_names_then_returns_empty_list(
        self, client, session, us_version  # noqa: F811
    ):
        """Empty names list → empty response (no DB query)."""
        data = client.post(
            "/parameters/by-name",
            json={"names": [], "tax_benefit_model_name": MODEL_NAMES["US"]},
        ).json()
        assert data == []

    def test_given_unknown_names_then_returns_empty_list(
        self, client, session, us_version  # noqa: F811
    ):
        """Names that don't match anything → empty list."""
        create_parameter(session, us_version, "gov.exists", "Exists")

        data = client.post(
            "/parameters/by-name",
            json={
                "names": ["gov.nope", "gov.also_missing"],
                "tax_benefit_model_name": MODEL_NAMES["US"],
            },
        ).json()
        assert data == []

    def test_given_mixed_names_then_returns_only_known(
        self, client, session, us_version  # noqa: F811
    ):
        """Only matching names are returned; unknowns silently omitted."""
        create_parameter(session, us_version, "gov.real", "Real")

        data = client.post(
            "/parameters/by-name",
            json={
                "names": ["gov.real", "gov.fake"],
                "tax_benefit_model_name": MODEL_NAMES["US"],
            },
        ).json()
        assert len(data) == 1
        assert data[0]["name"] == "gov.real"

    def test_given_single_name_then_returns_one(
        self, client, session, us_version  # noqa: F811
    ):
        """Single-element lookup works."""
        create_parameter(session, us_version, "gov.single", "Single")
        data = client.post(
            "/parameters/by-name",
            json={
                "names": ["gov.single"],
                "tax_benefit_model_name": MODEL_NAMES["US"],
            },
        ).json()
        assert len(data) == 1

    def test_results_ordered_by_name(
        self, client, session, us_version  # noqa: F811
    ):
        """Response is sorted alphabetically by name."""
        create_parameter(session, us_version, "gov.zzz", "Z")
        create_parameter(session, us_version, "gov.aaa", "A")
        create_parameter(session, us_version, "gov.mmm", "M")

        names = [
            p["name"]
            for p in client.post(
                "/parameters/by-name",
                json={
                    "names": ["gov.zzz", "gov.aaa", "gov.mmm"],
                    "tax_benefit_model_name": MODEL_NAMES["US"],
                },
            ).json()
        ]
        assert names == ["gov.aaa", "gov.mmm", "gov.zzz"]

    def test_response_shape(self, client, session, us_version):  # noqa: F811
        """Each returned object has the ParameterRead fields."""
        create_parameter(session, us_version, "gov.shape", "Shape")
        param = client.post(
            "/parameters/by-name",
            json={
                "names": ["gov.shape"],
                "tax_benefit_model_name": MODEL_NAMES["US"],
            },
        ).json()[0]
        for field in ("id", "name", "label", "created_at", "tax_benefit_model_version_id"):
            assert field in param


# -----------------------------------------------------------------------------
# Model isolation
# -----------------------------------------------------------------------------


class TestParametersByNameModelIsolation:
    def test_given_two_models_then_returns_only_requested(
        self, client, session, us_version, uk_version  # noqa: F811
    ):
        """Parameters from the other model are excluded."""
        create_parameter(session, us_version, "gov.shared", "US")
        create_parameter(session, uk_version, "gov.shared", "UK")

        data = client.post(
            "/parameters/by-name",
            json={
                "names": ["gov.shared"],
                "tax_benefit_model_name": MODEL_NAMES["UK"],
            },
        ).json()
        assert len(data) == 1
        assert data[0]["label"] == "UK"


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


class TestParametersByNameValidation:
    def test_given_missing_model_name_then_422(self, client):
        """Omitting tax_benefit_model_name → 422."""
        response = client.post(
            "/parameters/by-name", json={"names": ["gov.x"]}
        )
        assert response.status_code == 422

    def test_given_missing_names_then_422(self, client):
        """Omitting names → 422."""
        response = client.post(
            "/parameters/by-name",
            json={"tax_benefit_model_name": MODEL_NAMES["US"]},
        )
        assert response.status_code == 422

    def test_given_nonexistent_model_name_then_404(
        self, client, session
    ):
        """Model that doesn't exist → 404 from resolve_model_version_id."""
        response = client.post(
            "/parameters/by-name",
            json={
                "names": ["gov.x"],
                "tax_benefit_model_name": "nonexistent-model",
            },
        )
        assert response.status_code == 404


# -----------------------------------------------------------------------------
# Version filtering
# -----------------------------------------------------------------------------


class TestParametersByNameVersionFilter:
    def test_given_model_name_only_then_defaults_to_latest(
        self, client, session, us_two_versions  # noqa: F811
    ):
        """Model name resolves to latest version."""
        v1, v2 = us_two_versions
        create_parameter(session, v1, "gov.old", "Old")
        create_parameter(session, v2, "gov.new", "New")

        data = client.post(
            "/parameters/by-name",
            json={
                "names": ["gov.old", "gov.new"],
                "tax_benefit_model_name": MODEL_NAMES["US"],
            },
        ).json()
        assert len(data) == 1
        assert data[0]["name"] == "gov.new"

    def test_given_explicit_version_id_then_returns_that_version(
        self, client, session, us_two_versions  # noqa: F811
    ):
        """Explicit version_id overrides latest-version default."""
        v1, v2 = us_two_versions
        create_parameter(session, v1, "gov.old", "Old")
        create_parameter(session, v2, "gov.new", "New")

        data = client.post(
            "/parameters/by-name",
            json={
                "names": ["gov.old", "gov.new"],
                "tax_benefit_model_name": MODEL_NAMES["US"],
                "tax_benefit_model_version_id": str(v1.id),
            },
        ).json()
        assert len(data) == 1
        assert data[0]["name"] == "gov.old"
