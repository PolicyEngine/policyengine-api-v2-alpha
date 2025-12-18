"""Tests for dataset endpoints."""

from uuid import uuid4


def test_list_datasets(client):
    """List datasets returns a list."""
    response = client.get("/datasets")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_dataset_not_found(client):
    """Get a non-existent dataset returns 404."""
    fake_id = uuid4()
    response = client.get(f"/datasets/{fake_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Dataset not found"
