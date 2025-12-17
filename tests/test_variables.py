"""Tests for variable endpoints."""

from uuid import uuid4

import pytest


def test_list_variables(client):
    """List variables returns a list."""
    response = client.get("/variables")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_variable_not_found(client):
    """Get non-existent variable returns 404."""
    fake_id = uuid4()
    response = client.get(f"/variables/{fake_id}")
    assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
