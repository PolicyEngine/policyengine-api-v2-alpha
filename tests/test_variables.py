"""Tests for variable endpoints."""

from uuid import uuid4

import pytest

from test_fixtures.fixtures_parameters import (
    create_variable,
    two_model_versions,  # noqa: F401 - pytest fixture
)


# -----------------------------------------------------------------------------
# Variable Endpoint Basic Tests
# -----------------------------------------------------------------------------


def test__given_variables_endpoint_called__then_returns_list(client):
    """GET /variables returns a list."""
    # Given
    endpoint = "/variables"

    # When
    response = client.get(endpoint)

    # Then
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test__given_nonexistent_variable_id__then_returns_404(client):
    """GET /variables/{id} returns 404 for non-existent variable."""
    # Given
    fake_id = uuid4()

    # When
    response = client.get(f"/variables/{fake_id}")

    # Then
    assert response.status_code == 404


# -----------------------------------------------------------------------------
# Variable Version Filtering Tests
# -----------------------------------------------------------------------------


def test__given_model_name_filter__then_returns_only_latest_version_variables(
    client,
    session,
    two_model_versions,  # noqa: F811
):
    """GET /variables?tax_benefit_model_name=X returns only latest version variables."""
    # Given
    old_version = two_model_versions["old_version"]
    new_version = two_model_versions["new_version"]

    old_var = create_variable(session, old_version, "old_variable")
    new_var = create_variable(session, new_version, "new_variable")

    # When
    response = client.get("/variables?tax_benefit_model_name=policyengine-us")

    # Then
    assert response.status_code == 200
    data = response.json()
    var_ids = [v["id"] for v in data]
    assert str(new_var.id) in var_ids
    assert str(old_var.id) not in var_ids


def test__given_version_id_filter__then_returns_only_that_version_variables(
    client,
    session,
    two_model_versions,  # noqa: F811
):
    """GET /variables?tax_benefit_model_version_id=X returns only that version's variables."""
    # Given
    old_version = two_model_versions["old_version"]
    new_version = two_model_versions["new_version"]

    old_var = create_variable(session, old_version, "version_old_var")
    new_var = create_variable(session, new_version, "version_new_var")

    # When
    response = client.get(
        f"/variables?tax_benefit_model_version_id={old_version.id}"
    )

    # Then
    assert response.status_code == 200
    data = response.json()
    var_ids = [v["id"] for v in data]
    assert str(old_var.id) in var_ids
    assert str(new_var.id) not in var_ids


def test__given_both_model_name_and_version_id__then_version_id_takes_precedence(
    client,
    session,
    two_model_versions,  # noqa: F811
):
    """GET /variables with both filters uses version_id (takes precedence)."""
    # Given
    old_version = two_model_versions["old_version"]
    new_version = two_model_versions["new_version"]

    old_var = create_variable(session, old_version, "precedence_old_var")
    create_variable(session, new_version, "precedence_new_var")

    # When - pass both filters, version_id should win
    response = client.get(
        f"/variables?tax_benefit_model_name=policyengine-us"
        f"&tax_benefit_model_version_id={old_version.id}"
    )

    # Then - should get old version vars (version_id takes precedence)
    assert response.status_code == 200
    data = response.json()
    var_ids = [v["id"] for v in data]
    assert str(old_var.id) in var_ids


def test__given_nonexistent_model_name__then_returns_404(client):
    """GET /variables with non-existent model name returns 404."""
    # Given
    nonexistent_model = "nonexistent-model"

    # When
    response = client.get(f"/variables?tax_benefit_model_name={nonexistent_model}")

    # Then
    assert response.status_code == 404


def test__given_nonexistent_version_id__then_returns_404(client):
    """GET /variables with non-existent version ID returns 404."""
    # Given
    fake_version_id = uuid4()

    # When
    response = client.get(f"/variables?tax_benefit_model_version_id={fake_version_id}")

    # Then
    assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
