"""Tests for GET /parameter-values/ and GET /parameter-values/{id} endpoints."""

from datetime import datetime, timezone
from uuid import uuid4

from test_fixtures.fixtures_version_filter import (
    MODEL_NAMES,
    create_parameter,
    create_parameter_value,
    create_policy,
    us_model,  # noqa: F401
    us_two_versions,  # noqa: F401
    us_version,  # noqa: F401
)

# -----------------------------------------------------------------------------
# GET /parameter-values/ — basic
# -----------------------------------------------------------------------------


class TestListParameterValues:
    def test_given_no_values_then_returns_empty_list(self, client):
        """Empty database returns an empty list."""
        response = client.get("/parameter-values")
        assert response.status_code == 200
        assert response.json() == []

    def test_given_values_exist_then_returns_list(
        self,
        client,
        session,
        us_version,  # noqa: F811
    ):
        """Returns parameter values that exist."""
        param = create_parameter(session, us_version, "gov.rate", "Rate")
        create_parameter_value(session, param.id, 0.2)

        data = client.get("/parameter-values").json()
        assert len(data) == 1

    def test_given_parameter_id_then_filters_by_parameter(
        self,
        client,
        session,
        us_version,  # noqa: F811
    ):
        """Filters values to a specific parameter."""
        p1 = create_parameter(session, us_version, "gov.rate", "Rate")
        p2 = create_parameter(session, us_version, "gov.threshold", "Threshold")
        create_parameter_value(session, p1.id, 0.2)
        create_parameter_value(session, p2.id, 12570)

        data = client.get(f"/parameter-values?parameter_id={p1.id}").json()
        assert len(data) == 1
        assert data[0]["parameter_id"] == str(p1.id)

    def test_given_policy_id_then_filters_by_policy(
        self,
        client,
        session,
        us_version,  # noqa: F811
        us_model,  # noqa: F811
    ):
        """Filters values to a specific policy."""
        param = create_parameter(session, us_version, "gov.rate", "Rate")
        policy = create_policy(session, us_model, "Reform A")
        create_parameter_value(session, param.id, 0.2)
        create_parameter_value(session, param.id, 0.25, policy_id=policy.id)

        data = client.get(f"/parameter-values?policy_id={policy.id}").json()
        assert len(data) == 1
        assert data[0]["policy_id"] == str(policy.id)

    def test_given_combined_parameter_and_policy_filters(
        self,
        client,
        session,
        us_version,  # noqa: F811
        us_model,  # noqa: F811
    ):
        """parameter_id + policy_id work together."""
        p1 = create_parameter(session, us_version, "gov.rate", "Rate")
        p2 = create_parameter(session, us_version, "gov.threshold", "Threshold")
        policy = create_policy(session, us_model, "Reform A")
        create_parameter_value(session, p1.id, 0.2, policy_id=policy.id)
        create_parameter_value(session, p2.id, 12570, policy_id=policy.id)
        create_parameter_value(session, p1.id, 0.15)

        data = client.get(
            f"/parameter-values?parameter_id={p1.id}&policy_id={policy.id}"
        ).json()
        assert len(data) == 1

    def test_given_limit_then_returns_at_most_n(
        self,
        client,
        session,
        us_version,  # noqa: F811
    ):
        """Limit caps the number of results."""
        param = create_parameter(session, us_version, "gov.rate", "Rate")
        for i in range(5):
            create_parameter_value(
                session,
                param.id,
                i * 0.1,
                start_date=datetime(2020 + i, 1, 1, tzinfo=timezone.utc),
            )

        assert len(client.get("/parameter-values?limit=2").json()) == 2

    def test_given_skip_then_skips_first_n(
        self,
        client,
        session,
        us_version,  # noqa: F811
    ):
        """Skip omits the first N results."""
        param = create_parameter(session, us_version, "gov.rate", "Rate")
        for i in range(5):
            create_parameter_value(
                session,
                param.id,
                i * 0.1,
                start_date=datetime(2020 + i, 1, 1, tzinfo=timezone.utc),
            )

        assert len(client.get("/parameter-values?skip=3&limit=10").json()) == 2

    def test_results_ordered_by_start_date_desc(
        self,
        client,
        session,
        us_version,  # noqa: F811
    ):
        """Parameter values come back sorted by start_date descending."""
        param = create_parameter(session, us_version, "gov.rate", "Rate")
        create_parameter_value(
            session,
            param.id,
            0.1,
            start_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        create_parameter_value(
            session,
            param.id,
            0.2,
            start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )

        data = client.get("/parameter-values").json()
        assert len(data) == 2
        # Most recent first
        dates = [d["start_date"] for d in data]
        assert dates[0] > dates[1]


# -----------------------------------------------------------------------------
# GET /parameter-values/ — version filtering
# -----------------------------------------------------------------------------


class TestListParameterValuesVersionFilter:
    def test_given_model_name_then_returns_only_latest_version(
        self,
        client,
        session,
        us_two_versions,  # noqa: F811
    ):
        """Model name resolves to latest version; old-version param values excluded."""
        v1, v2 = us_two_versions
        p_old = create_parameter(session, v1, "gov.old", "Old")
        p_new = create_parameter(session, v2, "gov.new", "New")
        create_parameter_value(session, p_old.id, 0.1)
        create_parameter_value(session, p_new.id, 0.2)

        data = client.get(
            f"/parameter-values?tax_benefit_model_name={MODEL_NAMES['US']}"
        ).json()
        assert len(data) == 1
        assert data[0]["parameter_id"] == str(p_new.id)

    def test_given_explicit_version_id_then_returns_that_version(
        self,
        client,
        session,
        us_two_versions,  # noqa: F811
    ):
        """Explicit version_id pins to a specific version."""
        v1, v2 = us_two_versions
        p_old = create_parameter(session, v1, "gov.old", "Old")
        p_new = create_parameter(session, v2, "gov.new", "New")
        create_parameter_value(session, p_old.id, 0.1)
        create_parameter_value(session, p_new.id, 0.2)

        data = client.get(
            f"/parameter-values?tax_benefit_model_version_id={v1.id}"
        ).json()
        assert len(data) == 1
        assert data[0]["parameter_id"] == str(p_old.id)

    def test_given_both_then_version_id_takes_precedence(
        self,
        client,
        session,
        us_two_versions,  # noqa: F811
    ):
        """version_id overrides model_name."""
        v1, v2 = us_two_versions
        p_old = create_parameter(session, v1, "gov.old", "Old")
        p_new = create_parameter(session, v2, "gov.new", "New")
        create_parameter_value(session, p_old.id, 0.1)
        create_parameter_value(session, p_new.id, 0.2)

        data = client.get(
            f"/parameter-values?tax_benefit_model_name={MODEL_NAMES['US']}"
            f"&tax_benefit_model_version_id={v1.id}"
        ).json()
        assert len(data) == 1
        assert data[0]["parameter_id"] == str(p_old.id)

    def test_given_no_filters_then_returns_all_versions(
        self,
        client,
        session,
        us_two_versions,  # noqa: F811
    ):
        """Without model/version filter, values from all versions are returned."""
        v1, v2 = us_two_versions
        p_old = create_parameter(session, v1, "gov.old", "Old")
        p_new = create_parameter(session, v2, "gov.new", "New")
        create_parameter_value(session, p_old.id, 0.1)
        create_parameter_value(session, p_new.id, 0.2)

        data = client.get("/parameter-values").json()
        assert len(data) == 2

    def test_given_nonexistent_model_name_then_returns_404(self, client):
        """Unknown model name returns 404."""
        response = client.get(
            "/parameter-values?tax_benefit_model_name=nonexistent-model"
        )
        assert response.status_code == 404

    def test_given_version_filter_combined_with_parameter_id(
        self,
        client,
        session,
        us_two_versions,  # noqa: F811
    ):
        """Version filter + parameter_id work together."""
        v1, v2 = us_two_versions
        p1 = create_parameter(session, v2, "gov.rate", "Rate")
        p2 = create_parameter(session, v2, "gov.threshold", "Threshold")
        create_parameter_value(session, p1.id, 0.2)
        create_parameter_value(session, p2.id, 12570)

        data = client.get(
            f"/parameter-values?tax_benefit_model_name={MODEL_NAMES['US']}"
            f"&parameter_id={p1.id}"
        ).json()
        assert len(data) == 1
        assert data[0]["parameter_id"] == str(p1.id)


# -----------------------------------------------------------------------------
# GET /parameter-values/{id}
# -----------------------------------------------------------------------------


class TestGetParameterValue:
    def test_given_valid_id_then_returns_value(
        self,
        client,
        session,
        us_version,  # noqa: F811
    ):
        """Returns the full parameter value data."""
        param = create_parameter(session, us_version, "gov.rate", "Rate")
        pv = create_parameter_value(session, param.id, 0.2)

        response = client.get(f"/parameter-values/{pv.id}")
        assert response.status_code == 200
        assert response.json()["parameter_id"] == str(param.id)

    def test_given_nonexistent_id_then_returns_404(self, client):
        """Unknown UUID returns 404."""
        response = client.get(f"/parameter-values/{uuid4()}")
        assert response.status_code == 404

    def test_response_shape_matches_parameter_value_read(
        self,
        client,
        session,
        us_version,  # noqa: F811
    ):
        """Response contains all ParameterValueRead fields."""
        param = create_parameter(session, us_version, "gov.rate", "Rate")
        pv = create_parameter_value(session, param.id, 0.2)

        data = client.get(f"/parameter-values/{pv.id}").json()
        for field in ("id", "parameter_id", "value_json", "start_date", "created_at"):
            assert field in data
