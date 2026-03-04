"""Tests for GET /variables/ and GET /variables/{id} endpoints."""

from uuid import uuid4

from test_fixtures.fixtures_version_filter import (
    MODEL_NAMES,
    create_variable,
    us_model,  # noqa: F401
    us_two_versions,  # noqa: F401
    us_version,  # noqa: F401
)

# -----------------------------------------------------------------------------
# GET /variables/ — basic
# -----------------------------------------------------------------------------


class TestListVariables:
    def test_given_no_variables_then_returns_empty_list(self, client):
        """Empty database returns an empty list."""
        response = client.get("/variables")
        assert response.status_code == 200
        assert response.json() == []

    def test_given_variables_exist_then_returns_list(
        self,
        client,
        session,
        us_version,  # noqa: F811
    ):
        """Returns variables that exist."""
        create_variable(session, us_version, "employment_income")
        response = client.get("/variables")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_given_search_by_name_then_returns_matching(
        self,
        client,
        session,
        us_version,  # noqa: F811
    ):
        """Search filter matches variable name."""
        create_variable(session, us_version, "employment_income")
        create_variable(session, us_version, "income_tax")

        data = client.get("/variables?search=employment").json()
        assert len(data) == 1
        assert data[0]["name"] == "employment_income"

    def test_given_search_by_description_then_returns_matching(
        self,
        client,
        session,
        us_version,  # noqa: F811
    ):
        """Search filter matches variable description."""
        create_variable(
            session, us_version, "var_x", description="Total household income"
        )
        create_variable(session, us_version, "var_y", description="Tax liability")

        data = client.get("/variables?search=household").json()
        assert len(data) == 1
        assert data[0]["name"] == "var_x"

    def test_given_limit_then_returns_at_most_n(
        self,
        client,
        session,
        us_version,  # noqa: F811
    ):
        """Limit caps the number of results."""
        for i in range(5):
            create_variable(session, us_version, f"var_{i}")

        assert len(client.get("/variables?limit=2").json()) == 2

    def test_given_skip_then_skips_first_n(
        self,
        client,
        session,
        us_version,  # noqa: F811
    ):
        """Skip omits the first N results."""
        for i in range(5):
            create_variable(session, us_version, f"var_{i}")

        assert len(client.get("/variables?skip=3&limit=10").json()) == 2

    def test_results_ordered_by_name(
        self,
        client,
        session,
        us_version,  # noqa: F811
    ):
        """Variables come back sorted alphabetically by name."""
        create_variable(session, us_version, "zzz_var")
        create_variable(session, us_version, "aaa_var")
        names = [v["name"] for v in client.get("/variables").json()]
        assert names == ["aaa_var", "zzz_var"]


# -----------------------------------------------------------------------------
# GET /variables/ — version filtering
# -----------------------------------------------------------------------------


class TestListVariablesVersionFilter:
    def test_given_model_name_then_returns_only_latest_version(
        self,
        client,
        session,
        us_two_versions,  # noqa: F811
    ):
        """Model name resolves to latest version; old-version vars excluded."""
        v1, v2 = us_two_versions
        create_variable(session, v1, "old_variable")
        create_variable(session, v2, "new_variable")

        data = client.get(
            f"/variables?tax_benefit_model_name={MODEL_NAMES['US']}"
        ).json()
        assert len(data) == 1
        assert data[0]["name"] == "new_variable"

    def test_given_explicit_version_id_then_returns_that_version(
        self,
        client,
        session,
        us_two_versions,  # noqa: F811
    ):
        """Explicit version_id pins to a specific version."""
        v1, v2 = us_two_versions
        create_variable(session, v1, "old_variable")
        create_variable(session, v2, "new_variable")

        data = client.get(f"/variables?tax_benefit_model_version_id={v1.id}").json()
        assert len(data) == 1
        assert data[0]["name"] == "old_variable"

    def test_given_both_then_version_id_takes_precedence(
        self,
        client,
        session,
        us_two_versions,  # noqa: F811
    ):
        """version_id overrides model_name."""
        v1, v2 = us_two_versions
        create_variable(session, v1, "old_variable")
        create_variable(session, v2, "new_variable")

        data = client.get(
            f"/variables?tax_benefit_model_name={MODEL_NAMES['US']}"
            f"&tax_benefit_model_version_id={v1.id}"
        ).json()
        assert len(data) == 1
        assert data[0]["name"] == "old_variable"

    def test_given_no_filters_then_returns_all_versions(
        self,
        client,
        session,
        us_two_versions,  # noqa: F811
    ):
        """Without model/version filter, vars from all versions are returned."""
        v1, v2 = us_two_versions
        create_variable(session, v1, "old_variable")
        create_variable(session, v2, "new_variable")

        data = client.get("/variables").json()
        assert len(data) == 2

    def test_given_nonexistent_model_name_then_returns_404(self, client):
        """Unknown model name returns 404."""
        response = client.get("/variables?tax_benefit_model_name=nonexistent-model")
        assert response.status_code == 404

    def test_given_search_combined_with_version_filter(
        self,
        client,
        session,
        us_two_versions,  # noqa: F811
    ):
        """Search + version filter work together."""
        v1, v2 = us_two_versions
        create_variable(session, v2, "employment_income")
        create_variable(session, v2, "income_tax")

        data = client.get(
            f"/variables?tax_benefit_model_name={MODEL_NAMES['US']}&search=employment"
        ).json()
        assert len(data) == 1
        assert data[0]["name"] == "employment_income"


# -----------------------------------------------------------------------------
# GET /variables/{id}
# -----------------------------------------------------------------------------


class TestGetVariable:
    def test_given_valid_id_then_returns_variable(
        self,
        client,
        session,
        us_version,  # noqa: F811
    ):
        """Returns the full variable data."""
        var = create_variable(session, us_version, "employment_income")
        response = client.get(f"/variables/{var.id}")
        assert response.status_code == 200
        assert response.json()["name"] == "employment_income"

    def test_given_nonexistent_id_then_returns_404(self, client):
        """Unknown UUID returns 404."""
        response = client.get(f"/variables/{uuid4()}")
        assert response.status_code == 404

    def test_response_shape_matches_variable_read(
        self,
        client,
        session,
        us_version,  # noqa: F811
    ):
        """Response contains all VariableRead fields."""
        var = create_variable(session, us_version, "employment_income")
        data = client.get(f"/variables/{var.id}").json()
        for field in (
            "id",
            "name",
            "entity",
            "created_at",
            "tax_benefit_model_version_id",
        ):
            assert field in data
