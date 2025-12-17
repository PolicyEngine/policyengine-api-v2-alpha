"""Tests for tax benefit model endpoints."""

from uuid import uuid4

import pytest


def test_list_tax_benefit_models(client):
    """List tax benefit models returns a list."""
    response = client.get("/tax-benefit-models")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_tax_benefit_model_not_found(client):
    """Get non-existent tax benefit model returns 404."""
    fake_id = uuid4()
    response = client.get(f"/tax-benefit-models/{fake_id}")
    assert response.status_code == 404


def test_list_tax_benefit_model_versions(client):
    """List tax benefit model versions returns a list."""
    response = client.get("/tax-benefit-model-versions")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_tax_benefit_model_version_not_found(client):
    """Get non-existent version returns 404."""
    fake_id = uuid4()
    response = client.get(f"/tax-benefit-model-versions/{fake_id}")
    assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
