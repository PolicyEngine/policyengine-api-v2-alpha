"""Tests for simulation endpoints."""

from uuid import uuid4

import pytest


def test_list_simulations(client):
    """List simulations returns a list."""
    response = client.get("/simulations")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_simulation_not_found(client):
    """Get a non-existent simulation returns 404."""
    fake_id = uuid4()
    response = client.get(f"/simulations/{fake_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Simulation not found"
