"""Tests for POST /variables/by-name endpoint."""

import pytest

from test_fixtures.fixtures_version_filter import (
    MODEL_NAMES,
    create_variable,
    uk_model,  # noqa: F401
    uk_two_versions,  # noqa: F401
    uk_version,  # noqa: F401
    us_model,  # noqa: F401
    us_version,  # noqa: F401
)


# -----------------------------------------------------------------------------
# Happy-path lookups
# -----------------------------------------------------------------------------


class TestVariablesByName:
    def test_given_known_names_then_returns_matching(
        self, client, session, uk_version  # noqa: F811
    ):
        """Returns full metadata for each matching name."""
        create_variable(session, uk_version, "employment_income")
        create_variable(session, uk_version, "income_tax")

        data = client.post(
            "/variables/by-name",
            json={
                "names": ["employment_income", "income_tax"],
                "tax_benefit_model_name": MODEL_NAMES["UK"],
            },
        ).json()

        assert len(data) == 2
        assert {v["name"] for v in data} == {"employment_income", "income_tax"}

    def test_given_empty_names_then_returns_empty_list(
        self, client, session, uk_version  # noqa: F811
    ):
        """Empty names list returns empty response (no DB query)."""
        data = client.post(
            "/variables/by-name",
            json={"names": [], "tax_benefit_model_name": MODEL_NAMES["UK"]},
        ).json()
        assert data == []

    def test_given_unknown_names_then_returns_empty_list(
        self, client, session, uk_version  # noqa: F811
    ):
        """Names that don't match anything return empty list."""
        create_variable(session, uk_version, "employment_income")

        data = client.post(
            "/variables/by-name",
            json={
                "names": ["nonexistent_var", "also_missing"],
                "tax_benefit_model_name": MODEL_NAMES["UK"],
            },
        ).json()
        assert data == []

    def test_given_mixed_names_then_returns_only_known(
        self, client, session, uk_version  # noqa: F811
    ):
        """Only matching names are returned; unknowns silently omitted."""
        create_variable(session, uk_version, "income_tax")

        data = client.post(
            "/variables/by-name",
            json={
                "names": ["income_tax", "fake_var"],
                "tax_benefit_model_name": MODEL_NAMES["UK"],
            },
        ).json()
        assert len(data) == 1
        assert data[0]["name"] == "income_tax"

    def test_given_single_name_then_returns_one(
        self, client, session, uk_version  # noqa: F811
    ):
        """Single-element lookup works."""
        create_variable(session, uk_version, "age")
        data = client.post(
            "/variables/by-name",
            json={
                "names": ["age"],
                "tax_benefit_model_name": MODEL_NAMES["UK"],
            },
        ).json()
        assert len(data) == 1

    def test_results_ordered_by_name(
        self, client, session, uk_version  # noqa: F811
    ):
        """Response is sorted alphabetically by name."""
        create_variable(session, uk_version, "zzz_var")
        create_variable(session, uk_version, "aaa_var")
        create_variable(session, uk_version, "mmm_var")

        names = [
            v["name"]
            for v in client.post(
                "/variables/by-name",
                json={
                    "names": ["zzz_var", "aaa_var", "mmm_var"],
                    "tax_benefit_model_name": MODEL_NAMES["UK"],
                },
            ).json()
        ]
        assert names == ["aaa_var", "mmm_var", "zzz_var"]

    def test_response_shape(self, client, session, uk_version):  # noqa: F811
        """Each returned object has the VariableRead fields."""
        create_variable(
            session, uk_version, "income_tax", entity="person", description="Tax"
        )
        var = client.post(
            "/variables/by-name",
            json={
                "names": ["income_tax"],
                "tax_benefit_model_name": MODEL_NAMES["UK"],
            },
        ).json()[0]
        for field in ("id", "name", "entity", "description", "created_at", "tax_benefit_model_version_id"):
            assert field in var


# -----------------------------------------------------------------------------
# Model isolation
# -----------------------------------------------------------------------------


class TestVariablesByNameModelIsolation:
    def test_given_two_models_then_returns_only_requested(
        self, client, session, uk_version, us_version  # noqa: F811
    ):
        """Variables from the other model are excluded."""
        create_variable(session, uk_version, "council_tax")
        create_variable(session, us_version, "state_income_tax")

        uk_data = client.post(
            "/variables/by-name",
            json={
                "names": ["council_tax", "state_income_tax"],
                "tax_benefit_model_name": MODEL_NAMES["UK"],
            },
        ).json()
        us_data = client.post(
            "/variables/by-name",
            json={
                "names": ["council_tax", "state_income_tax"],
                "tax_benefit_model_name": MODEL_NAMES["US"],
            },
        ).json()

        assert len(uk_data) == 1
        assert uk_data[0]["name"] == "council_tax"
        assert len(us_data) == 1
        assert us_data[0]["name"] == "state_income_tax"


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


class TestVariablesByNameValidation:
    def test_given_missing_model_name_then_422(self, client):
        """Omitting tax_benefit_model_name returns 422."""
        response = client.post(
            "/variables/by-name", json={"names": ["income_tax"]}
        )
        assert response.status_code == 422

    def test_given_missing_names_then_422(self, client):
        """Omitting names returns 422."""
        response = client.post(
            "/variables/by-name",
            json={"tax_benefit_model_name": MODEL_NAMES["UK"]},
        )
        assert response.status_code == 422

    def test_given_nonexistent_model_name_then_404(self, client, session):
        """Model that doesn't exist returns 404."""
        response = client.post(
            "/variables/by-name",
            json={
                "names": ["income_tax"],
                "tax_benefit_model_name": "nonexistent-model",
            },
        )
        assert response.status_code == 404


# -----------------------------------------------------------------------------
# Version filtering
# -----------------------------------------------------------------------------


class TestVariablesByNameVersionFilter:
    def test_given_model_name_only_then_defaults_to_latest(
        self, client, session, uk_two_versions  # noqa: F811
    ):
        """Model name resolves to latest version."""
        v1, v2 = uk_two_versions
        create_variable(session, v1, "old_var")
        create_variable(session, v2, "new_var")

        data = client.post(
            "/variables/by-name",
            json={
                "names": ["old_var", "new_var"],
                "tax_benefit_model_name": MODEL_NAMES["UK"],
            },
        ).json()
        assert len(data) == 1
        assert data[0]["name"] == "new_var"

    def test_given_explicit_version_id_then_returns_that_version(
        self, client, session, uk_two_versions  # noqa: F811
    ):
        """Explicit version_id overrides latest-version default."""
        v1, v2 = uk_two_versions
        create_variable(session, v1, "old_var")
        create_variable(session, v2, "new_var")

        data = client.post(
            "/variables/by-name",
            json={
                "names": ["old_var", "new_var"],
                "tax_benefit_model_name": MODEL_NAMES["UK"],
                "tax_benefit_model_version_id": str(v1.id),
            },
        ).json()
        assert len(data) == 1
        assert data[0]["name"] == "old_var"
