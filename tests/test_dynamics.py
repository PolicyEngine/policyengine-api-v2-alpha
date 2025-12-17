"""Tests for dynamics endpoints."""

from uuid import uuid4

import pytest


def test_list_dynamics(client):
    """List dynamics returns a list."""
    response = client.get("/dynamics")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_dynamic(client):
    """Create a new dynamic model."""
    response = client.post(
        "/dynamics",
        json={
            "name": "Test dynamic",
            "description": "A test dynamic model",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test dynamic"
    assert data["description"] == "A test dynamic model"
    assert "id" in data


def test_get_dynamic_not_found(client):
    """Get non-existent dynamic returns 404."""
    fake_id = uuid4()
    response = client.get(f"/dynamics/{fake_id}")
    assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
