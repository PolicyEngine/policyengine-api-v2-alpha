"""Tests for policy endpoints."""

from uuid import uuid4

from policyengine_api.models import Policy


def test_list_policies_empty(client):
    """List policies returns empty list when no policies exist."""
    response = client.get("/policies")
    assert response.status_code == 200
    assert response.json() == []


def test_create_policy(client):
    """Create a new policy."""
    response = client.post(
        "/policies",
        json={
            "name": "Test policy",
            "description": "A test policy",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test policy"
    assert data["description"] == "A test policy"
    assert "id" in data


def test_list_policies_with_data(client, session):
    """List policies returns all policies."""
    policy = Policy(name="test-policy", description="Test")
    session.add(policy)
    session.commit()

    response = client.get("/policies")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "test-policy"


def test_get_policy(client, session):
    """Get a specific policy by ID."""
    policy = Policy(name="test-policy", description="Test")
    session.add(policy)
    session.commit()
    session.refresh(policy)

    response = client.get(f"/policies/{policy.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test-policy"
    assert data["id"] == str(policy.id)


def test_get_policy_not_found(client):
    """Get a non-existent policy returns 404."""
    fake_id = uuid4()
    response = client.get(f"/policies/{fake_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Policy not found"
