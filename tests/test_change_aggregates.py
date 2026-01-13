"""Tests for change aggregate endpoints."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


def test_list_change_aggregates_empty(client):
    """List change aggregates returns empty list initially."""
    response = client.get("/outputs/change-aggregates")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@patch("policyengine_api.api.change_aggregates.modal.Function")
def test_create_single_change_aggregate(mock_modal_fn, client, simulation_id):
    """Create a single change aggregate."""
    mock_fn = MagicMock()
    mock_modal_fn.from_name.return_value = mock_fn

    response = client.post(
        "/outputs/change-aggregates",
        json=[
            {
                "baseline_simulation_id": simulation_id,
                "reform_simulation_id": simulation_id,
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


@patch("policyengine_api.api.change_aggregates.modal.Function")
def test_create_multiple_change_aggregates(mock_modal_fn, client, simulation_id):
    """Create multiple change aggregates in one request."""
    mock_fn = MagicMock()
    mock_modal_fn.from_name.return_value = mock_fn

    response = client.post(
        "/outputs/change-aggregates",
        json=[
            {
                "baseline_simulation_id": simulation_id,
                "reform_simulation_id": simulation_id,
                "variable": "income_tax",
                "aggregate_type": "sum",
            },
            {
                "baseline_simulation_id": simulation_id,
                "reform_simulation_id": simulation_id,
                "variable": "benefits",
                "aggregate_type": "mean",
            },
        ],
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_get_change_aggregate_not_found(client):
    """Get non-existent change aggregate returns 404."""
    fake_id = uuid4()
    response = client.get(f"/outputs/change-aggregates/{fake_id}")
    assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
