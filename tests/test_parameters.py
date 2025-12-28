"""Tests for parameter and parameter-value endpoints."""

from uuid import uuid4

import pytest

from test_fixtures.fixtures_parameters import (
    create_parameter,
    create_parameter_value,
    create_parameter_values_batch,
    create_policy,
    model_version,  # noqa: F401 - pytest fixture
)

# -----------------------------------------------------------------------------
# Parameter Endpoint Tests
# -----------------------------------------------------------------------------


def test__given_parameters_endpoint_called__then_returns_list(client):
    """GET /parameters returns a list."""
    # Given
    endpoint = "/parameters"

    # When
    response = client.get(endpoint)

    # Then
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test__given_nonexistent_parameter_id__then_returns_404(client):
    """GET /parameters/{id} returns 404 for non-existent parameter."""
    # Given
    fake_id = uuid4()

    # When
    response = client.get(f"/parameters/{fake_id}")

    # Then
    assert response.status_code == 404


# -----------------------------------------------------------------------------
# Parameter Value Endpoint Tests
# -----------------------------------------------------------------------------


def test__given_parameter_values_endpoint_called__then_returns_list(client):
    """GET /parameter-values returns a list."""
    # Given
    endpoint = "/parameter-values"

    # When
    response = client.get(endpoint)

    # Then
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test__given_nonexistent_parameter_value_id__then_returns_404(client):
    """GET /parameter-values/{id} returns 404 for non-existent parameter value."""
    # Given
    fake_id = uuid4()

    # When
    response = client.get(f"/parameter-values/{fake_id}")

    # Then
    assert response.status_code == 404


# -----------------------------------------------------------------------------
# Parameter Value Filtering Tests
# -----------------------------------------------------------------------------


def test__given_parameter_id_filter__then_returns_only_matching_values(
    client,
    session,
    model_version,  # noqa: F811
):
    """GET /parameter-values?parameter_id=X returns only values for that parameter."""
    # Given
    param1 = create_parameter(session, model_version, "test.param1", "Test Param 1")
    param2 = create_parameter(session, model_version, "test.param2", "Test Param 2")
    create_parameter_value(session, param1.id, 100)
    create_parameter_value(session, param2.id, 200)

    # When
    response = client.get(f"/parameter-values?parameter_id={param1.id}")

    # Then
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["parameter_id"] == str(param1.id)


def test__given_policy_id_filter__then_returns_only_matching_values(
    client,
    session,
    model_version,  # noqa: F811
):
    """GET /parameter-values?policy_id=X returns only values for that policy."""
    # Given
    param = create_parameter(session, model_version, "test.param", "Test Param")
    policy = create_policy(session, "Test Policy")
    create_parameter_value(session, param.id, 100, policy_id=None)  # baseline
    create_parameter_value(session, param.id, 150, policy_id=policy.id)  # reform

    # When
    response = client.get(f"/parameter-values?policy_id={policy.id}")

    # Then
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["policy_id"] == str(policy.id)
    assert data[0]["value_json"] == 150


def test__given_both_parameter_and_policy_filters__then_returns_matching_intersection(
    client,
    session,
    model_version,  # noqa: F811
):
    """GET /parameter-values?parameter_id=X&policy_id=Y returns intersection."""
    # Given
    param1 = create_parameter(
        session, model_version, "test.both.param1", "Test Both Param 1"
    )
    param2 = create_parameter(
        session, model_version, "test.both.param2", "Test Both Param 2"
    )
    policy = create_policy(session, "Test Both Policy")

    create_parameter_value(session, param1.id, 100, policy_id=None)  # baseline
    create_parameter_value(session, param1.id, 150, policy_id=policy.id)  # target
    create_parameter_value(session, param2.id, 200, policy_id=policy.id)  # other

    # When
    response = client.get(
        f"/parameter-values?parameter_id={param1.id}&policy_id={policy.id}"
    )

    # Then
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["parameter_id"] == str(param1.id)
    assert data[0]["policy_id"] == str(policy.id)
    assert data[0]["value_json"] == 150


# -----------------------------------------------------------------------------
# Parameter Value Pagination Tests
# -----------------------------------------------------------------------------


def test__given_limit_parameter__then_returns_limited_results(
    client,
    session,
    model_version,  # noqa: F811
):
    """GET /parameter-values?limit=N returns at most N results."""
    # Given
    param = create_parameter(
        session, model_version, "test.pagination.param", "Test Pagination Param"
    )
    create_parameter_values_batch(session, param.id, count=5)

    # When
    response = client.get(f"/parameter-values?parameter_id={param.id}&limit=2")

    # Then
    assert response.status_code == 200
    assert len(response.json()) == 2


def test__given_skip_parameter__then_skips_specified_results(
    client,
    session,
    model_version,  # noqa: F811
):
    """GET /parameter-values?skip=N skips first N results."""
    # Given
    param = create_parameter(
        session, model_version, "test.skip.param", "Test Skip Param"
    )
    create_parameter_values_batch(session, param.id, count=5)

    # When
    response = client.get(f"/parameter-values?parameter_id={param.id}&skip=3&limit=10")

    # Then
    assert response.status_code == 200
    assert len(response.json()) == 2  # 5 total - 3 skipped = 2 remaining


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
