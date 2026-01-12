"""Tests for aggregate outputs endpoints."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from test_fixtures.fixtures_parameters import (
    create_dataset,
    create_model_and_version,
    create_simulation,
    simulation_fixture,  # noqa: F401 - pytest fixture
)


def test_list_aggregates_empty(client):
    """List aggregates returns empty list initially."""
    # Given
    endpoint = "/outputs/aggregates"

    # When
    response = client.get(endpoint)

    # Then
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("policyengine_api.api.outputs.modal.Function.from_name")
def test__given_valid_simulation__when_creating_single_aggregate__then_returns_200(
    mock_modal_function,
    client,
    session,
    simulation_fixture,  # noqa: F811
):
    """Create a single aggregate output with valid simulation."""
    # Given
    mock_fn = MagicMock()
    mock_modal_function.return_value = mock_fn
    simulation = simulation_fixture["simulation"]

    # When
    response = client.post(
        "/outputs/aggregates",
        json=[
            {
                "simulation_id": str(simulation.id),
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


@patch("policyengine_api.api.outputs.modal.Function.from_name")
def test__given_valid_simulation__when_creating_multiple_aggregates__then_returns_200(
    mock_modal_function,
    client,
    session,
    simulation_fixture,  # noqa: F811
):
    """Create multiple aggregate outputs in one request with valid simulation."""
    # Given
    mock_fn = MagicMock()
    mock_modal_function.return_value = mock_fn
    simulation = simulation_fixture["simulation"]

    # When
    response = client.post(
        "/outputs/aggregates",
        json=[
            {
                "simulation_id": str(simulation.id),
                "variable": "income_tax",
                "aggregate_type": "sum",
            },
            {
                "simulation_id": str(simulation.id),
                "variable": "household_count",
                "aggregate_type": "count",
            },
            {
                "simulation_id": str(simulation.id),
                "variable": "mean_income",
                "aggregate_type": "mean",
            },
        ],
    )

    # Then
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    variables = {d["variable"] for d in data}
    assert variables == {"income_tax", "household_count", "mean_income"}
    assert mock_fn.spawn.call_count == 3


def test__given_nonexistent_simulation__when_creating_aggregate__then_returns_404(
    client,
):
    """Create aggregate with non-existent simulation returns 404."""
    # Given
    fake_simulation_id = uuid4()

    # When
    response = client.post(
        "/outputs/aggregates",
        json=[
            {
                "simulation_id": str(fake_simulation_id),
                "variable": "net_income",
                "aggregate_type": "sum",
            }
        ],
    )

    # Then
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_aggregate_not_found(client):
    """Get non-existent aggregate returns 404."""
    # Given
    fake_id = uuid4()

    # When
    response = client.get(f"/outputs/aggregates/{fake_id}")

    # Then
    assert response.status_code == 404
    assert response.json()["detail"] == "Aggregate not found"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
