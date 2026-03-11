"""Tests for variable label field across all variable endpoints."""

from test_fixtures.fixtures_variables import (  # noqa: F811
    create_variable,
)

# ---------------------------------------------------------------------------
# GET /variables - label in list responses
# ---------------------------------------------------------------------------


class TestListVariablesLabel:
    """Tests that label is returned when listing variables."""

    def test_label_returned_in_response(
        self,
        client,
        session,
        us_model_version,  # noqa: F811
    ):
        """Variable with a label should include it in the list response."""
        create_variable(
            session,
            us_model_version,
            name="employment_income",
            label="Employment income",
        )

        response = client.get("/variables")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["label"] == "Employment income"

    def test_null_label_returned_when_absent(
        self,
        client,
        session,
        us_model_version,  # noqa: F811
    ):
        """Variable without a label should return null."""
        create_variable(
            session,
            us_model_version,
            name="age",
            label=None,
        )

        response = client.get("/variables")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["label"] is None

    def test_empty_label_returned(
        self,
        client,
        session,
        us_model_version,  # noqa: F811
    ):
        """Variable with an empty string label should return it as-is."""
        create_variable(
            session,
            us_model_version,
            name="household_weight",
            label="",
        )

        response = client.get("/variables")
        assert response.status_code == 200
        assert response.json()[0]["label"] == ""


# ---------------------------------------------------------------------------
# GET /variables?search= - search by label
# ---------------------------------------------------------------------------


class TestSearchVariablesByLabel:
    """Tests that the search parameter matches against labels."""

    def test_search_matches_label(
        self,
        client,
        session,
        us_model_version,  # noqa: F811
    ):
        """Searching for a term in the label should return the variable."""
        create_variable(
            session,
            us_model_version,
            name="employment_income",
            label="Employment income",
        )
        create_variable(
            session,
            us_model_version,
            name="age",
            label="Age of person",
        )

        response = client.get(
            "/variables",
            params={
                "search": "Employment",
                "tax_benefit_model_name": "policyengine-us",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "employment_income"

    def test_search_label_case_insensitive(
        self,
        client,
        session,
        us_model_version,  # noqa: F811
    ):
        """Label search should be case-insensitive."""
        create_variable(
            session,
            us_model_version,
            name="income_tax",
            label="Income tax",
        )

        response = client.get(
            "/variables",
            params={
                "search": "INCOME TAX",
                "tax_benefit_model_name": "policyengine-us",
            },
        )
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_search_partial_label_match(
        self,
        client,
        session,
        us_model_version,  # noqa: F811
    ):
        """Partial label matches should be returned."""
        create_variable(
            session,
            us_model_version,
            name="state_income_tax",
            label="State income tax",
        )

        response = client.get(
            "/variables",
            params={
                "search": "income",
                "tax_benefit_model_name": "policyengine-us",
            },
        )
        assert response.status_code == 200
        assert len(response.json()) == 1


# ---------------------------------------------------------------------------
# GET /variables/{id} - label in single variable response
# ---------------------------------------------------------------------------


class TestGetVariableLabel:
    """Tests that label is returned when fetching a single variable."""

    def test_label_in_get_response(
        self,
        client,
        session,
        us_model_version,  # noqa: F811
    ):
        """GET /variables/{id} should include the label field."""
        var = create_variable(
            session,
            us_model_version,
            name="employment_income",
            label="Employment income",
        )

        response = client.get(f"/variables/{var.id}")
        assert response.status_code == 200
        assert response.json()["label"] == "Employment income"

    def test_null_label_in_get_response(
        self,
        client,
        session,
        us_model_version,  # noqa: F811
    ):
        """GET /variables/{id} should return null for missing label."""
        var = create_variable(
            session,
            us_model_version,
            name="age",
            label=None,
        )

        response = client.get(f"/variables/{var.id}")
        assert response.status_code == 200
        assert response.json()["label"] is None


# ---------------------------------------------------------------------------
# POST /variables/by-name - label in batch lookup
# ---------------------------------------------------------------------------


class TestVariablesByNameLabel:
    """Tests that label is included in by-name lookup responses."""

    def test_label_in_by_name_response(
        self,
        client,
        session,
        us_model_version,  # noqa: F811
    ):
        """POST /variables/by-name should include the label field."""
        create_variable(
            session,
            us_model_version,
            name="employment_income",
            label="Employment income",
        )

        response = client.post(
            "/variables/by-name",
            json={"names": ["employment_income"], "country_id": "us"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["label"] == "Employment income"

    def test_mixed_labels_in_by_name_response(
        self,
        client,
        session,
        us_model_version,  # noqa: F811
    ):
        """Variables with and without labels should both be returned correctly."""
        create_variable(
            session,
            us_model_version,
            name="employment_income",
            label="Employment income",
        )
        create_variable(
            session,
            us_model_version,
            name="age",
            label=None,
        )

        response = client.post(
            "/variables/by-name",
            json={"names": ["employment_income", "age"], "country_id": "us"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        by_name = {v["name"]: v for v in data}
        assert by_name["employment_income"]["label"] == "Employment income"
        assert by_name["age"]["label"] is None


# ---------------------------------------------------------------------------
# Country isolation for labels
# ---------------------------------------------------------------------------


class TestVariableLabelCountryIsolation:
    """Tests that label search respects country boundaries."""

    def test_search_by_label_isolated_by_country(
        self,
        client,
        session,
        us_model_version,  # noqa: F811
        uk_model_version,  # noqa: F811
    ):
        """Searching by label should only return variables from the specified country."""
        create_variable(
            session,
            us_model_version,
            name="state_income_tax",
            label="State income tax",
        )
        create_variable(
            session,
            uk_model_version,
            name="council_tax",
            label="Council tax",
        )

        us_response = client.get(
            "/variables",
            params={
                "search": "tax",
                "tax_benefit_model_name": "policyengine-us",
            },
        )
        uk_response = client.get(
            "/variables",
            params={
                "search": "tax",
                "tax_benefit_model_name": "policyengine-uk",
            },
        )

        us_names = {v["name"] for v in us_response.json()}
        uk_names = {v["name"] for v in uk_response.json()}

        assert "state_income_tax" in us_names
        assert "council_tax" not in us_names
        assert "council_tax" in uk_names
        assert "state_income_tax" not in uk_names
