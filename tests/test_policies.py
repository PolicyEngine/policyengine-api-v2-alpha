"""Tests for policy endpoints."""

from uuid import uuid4

from policyengine_api.models import Policy, TaxBenefitModel


def test_list_policies_empty(client):
    """List policies returns empty list when no policies exist."""
    response = client.get("/policies")
    assert response.status_code == 200
    assert response.json() == []


def test_create_policy(client, tax_benefit_model):
    """Create a new policy."""
    response = client.post(
        "/policies",
        json={
            "name": "Test policy",
            "description": "A test policy",
            "tax_benefit_model_id": str(tax_benefit_model.id),
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test policy"
    assert data["description"] == "A test policy"
    assert data["tax_benefit_model_id"] == str(tax_benefit_model.id)
    assert "id" in data


def test_create_policy_invalid_tax_benefit_model(client):
    """Create policy with non-existent tax_benefit_model returns 404."""
    fake_id = uuid4()
    response = client.post(
        "/policies",
        json={
            "name": "Test policy",
            "description": "A test policy",
            "tax_benefit_model_id": str(fake_id),
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Tax benefit model not found"


def test_list_policies_with_data(client, session, tax_benefit_model):
    """List policies returns all policies."""
    policy = Policy(
        name="test-policy",
        description="Test",
        tax_benefit_model_id=tax_benefit_model.id,
    )
    session.add(policy)
    session.commit()

    response = client.get("/policies")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "test-policy"


def test_list_policies_filter_by_tax_benefit_model(
    client, session, tax_benefit_model, uk_tax_benefit_model
):
    """List policies with tax_benefit_model_id filter."""
    policy1 = Policy(
        name="US policy",
        description="US",
        tax_benefit_model_id=tax_benefit_model.id,
    )
    policy2 = Policy(
        name="UK policy",
        description="UK",
        tax_benefit_model_id=uk_tax_benefit_model.id,
    )
    session.add(policy1)
    session.add(policy2)
    session.commit()

    # Filter by US model
    response = client.get(f"/policies?tax_benefit_model_id={tax_benefit_model.id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "US policy"


def test_get_policy(client, session, tax_benefit_model):
    """Get a specific policy by ID."""
    policy = Policy(
        name="test-policy",
        description="Test",
        tax_benefit_model_id=tax_benefit_model.id,
    )
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
