"""Tests for parameter endpoints."""

from uuid import uuid4

import pytest


def test_list_parameters(client):
    """List parameters returns a list."""
    response = client.get("/parameters")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_parameter_not_found(client):
    """Get non-existent parameter returns 404."""
    fake_id = uuid4()
    response = client.get(f"/parameters/{fake_id}")
    assert response.status_code == 404


def test_list_parameter_values(client):
    """List parameter values returns a list."""
    response = client.get("/parameter-values")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
