"""Tests for change aggregate endpoints."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from test_fixtures.fixtures_parameters import (
    create_dataset,
    create_model_and_version,
    create_simulation,
)


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def two_simulations(session):
    """Create two simulations (baseline and reform) for change aggregate tests."""
    model, version = create_model_and_version(
        session,
        model_name="policyengine-uk",
        version_string="1.0.0",
    )
    dataset = create_dataset(session, model, name="test-frs-2024")
    baseline = create_simulation(session, dataset, version)
    reform = create_simulation(session, dataset, version)
    return {
        "baseline": baseline,
        "reform": reform,
    }


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


def test_list_change_aggregates_empty(client):
    """List change aggregates returns empty list initially."""
    # Given
    endpoint = "/outputs/change-aggregates"

    # When
    response = client.get(endpoint)

    # Then
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("policyengine_api.api.change_aggregates.modal.Function.from_name")
def test__given_valid_simulations__when_creating_single_change_aggregate__then_returns_200(
    mock_modal_function,
    client,
    session,
    two_simulations,
):
    """Create a single change aggregate with valid simulations."""
    # Given
    mock_fn = MagicMock()
    mock_modal_function.return_value = mock_fn
    baseline = two_simulations["baseline"]
    reform = two_simulations["reform"]

    # When
    response = client.post(
        "/outputs/change-aggregates",
        json=[
            {
                "baseline_simulation_id": str(baseline.id),
                "reform_simulation_id": str(reform.id),
                "variable": "net_income",
                "aggregate_type": "sum",
            }
        ],
    )

    # Then
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["variable"] == "net_income"
    assert data[0]["aggregate_type"] == "sum"
    mock_fn.spawn.assert_called_once()


@patch("policyengine_api.api.change_aggregates.modal.Function.from_name")
def test__given_valid_simulations__when_creating_multiple_change_aggregates__then_returns_200(
    mock_modal_function,
    client,
    session,
    two_simulations,
):
    """Create multiple change aggregates in one request with valid simulations."""
    # Given
    mock_fn = MagicMock()
    mock_modal_function.return_value = mock_fn
    baseline = two_simulations["baseline"]
    reform = two_simulations["reform"]

    # When
    response = client.post(
        "/outputs/change-aggregates",
        json=[
            {
                "baseline_simulation_id": str(baseline.id),
                "reform_simulation_id": str(reform.id),
                "variable": "income_tax",
                "aggregate_type": "sum",
            },
            {
                "baseline_simulation_id": str(baseline.id),
                "reform_simulation_id": str(reform.id),
                "variable": "benefits",
                "aggregate_type": "mean",
            },
        ],
    )

    # Then
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert mock_fn.spawn.call_count == 2


def test__given_nonexistent_baseline_simulation__when_creating_change_aggregate__then_returns_404(
    client,
    session,
    two_simulations,
):
    """Create change aggregate with non-existent baseline simulation returns 404."""
    # Given
    reform = two_simulations["reform"]
    fake_baseline_id = uuid4()

    # When
    response = client.post(
        "/outputs/change-aggregates",
        json=[
            {
                "baseline_simulation_id": str(fake_baseline_id),
                "reform_simulation_id": str(reform.id),
                "variable": "net_income",
                "aggregate_type": "sum",
            }
        ],
    )

    # Then
    assert response.status_code == 404
    assert "baseline" in response.json()["detail"].lower()


def test__given_nonexistent_reform_simulation__when_creating_change_aggregate__then_returns_404(
    client,
    session,
    two_simulations,
):
    """Create change aggregate with non-existent reform simulation returns 404."""
    # Given
    baseline = two_simulations["baseline"]
    fake_reform_id = uuid4()

    # When
    response = client.post(
        "/outputs/change-aggregates",
        json=[
            {
                "baseline_simulation_id": str(baseline.id),
                "reform_simulation_id": str(fake_reform_id),
                "variable": "net_income",
                "aggregate_type": "sum",
            }
        ],
    )

    # Then
    assert response.status_code == 404
    assert "reform" in response.json()["detail"].lower()


def test_get_change_aggregate_not_found(client):
    """Get non-existent change aggregate returns 404."""
    # Given
    fake_id = uuid4()

    # When
    response = client.get(f"/outputs/change-aggregates/{fake_id}")

    # Then
    assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
