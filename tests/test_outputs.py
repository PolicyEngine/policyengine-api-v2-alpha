"""Tests for aggregate outputs endpoints."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


def test_list_aggregates_empty(client):
    """List aggregates returns empty list initially."""
    response = client.get("/outputs/aggregates")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("policyengine_api.api.outputs.modal.Function")
def test_create_single_aggregate(mock_modal_fn, client, simulation_id):
    """Create a single aggregate output."""
    mock_fn = MagicMock()
    mock_modal_fn.from_name.return_value = mock_fn

    response = client.post(
        "/outputs/aggregates",
        json=[
            {
                "simulation_id": simulation_id,
                "variable": "net_income",
                "aggregate_type": "sum",
            }
        ],
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["variable"] == "net_income"
    assert data[0]["aggregate_type"] == "sum"


@patch("policyengine_api.api.outputs.modal.Function")
def test_create_multiple_aggregates(mock_modal_fn, client, simulation_id):
    """Create multiple aggregate outputs in one request."""
    mock_fn = MagicMock()
    mock_modal_fn.from_name.return_value = mock_fn

    response = client.post(
        "/outputs/aggregates",
        json=[
            {
                "simulation_id": simulation_id,
                "variable": "income_tax",
                "aggregate_type": "sum",
            },
            {
                "simulation_id": simulation_id,
                "variable": "household_count",
                "aggregate_type": "count",
            },
            {
                "simulation_id": simulation_id,
                "variable": "mean_income",
                "aggregate_type": "mean",
            },
        ],
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    variables = {d["variable"] for d in data}
    assert variables == {"income_tax", "household_count", "mean_income"}


def test_get_aggregate_not_found(client):
    """Get non-existent aggregate returns 404."""
    fake_id = uuid4()
    response = client.get(f"/outputs/aggregates/{fake_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Aggregate not found"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
