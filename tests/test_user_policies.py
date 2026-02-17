"""Tests for user-policy association endpoints.

Note: user_id is a client-generated UUID (not validated against users table),
so tests use uuid4() directly rather than creating User records.
"""

from uuid import uuid4

from test_fixtures.fixtures_user_policies import (
    UK_COUNTRY_ID,
    US_COUNTRY_ID,
    create_policy,
    create_user_policy,
)


def test_list_user_policies_empty(client):
    """List user policies returns empty list when user has no associations."""
    user_id = uuid4()
    response = client.get(f"/user-policies?user_id={user_id}")
    assert response.status_code == 200
    assert response.json() == []


def test_create_user_policy(client, session, tax_benefit_model):
    """Create a new user-policy association."""
    user_id = uuid4()
    policy = create_policy(session, tax_benefit_model)

    response = client.post(
        "/user-policies",
        json={
            "user_id": str(user_id),
            "policy_id": str(policy.id),
            "country_id": US_COUNTRY_ID,
            "label": "My test policy",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(user_id)
    assert data["policy_id"] == str(policy.id)
    assert data["country_id"] == US_COUNTRY_ID
    assert data["label"] == "My test policy"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_user_policy_without_label(client, session, tax_benefit_model):
    """Create a user-policy association without a label."""
    user_id = uuid4()
    policy = create_policy(session, tax_benefit_model)

    response = client.post(
        "/user-policies",
        json={
            "user_id": str(user_id),
            "policy_id": str(policy.id),
            "country_id": US_COUNTRY_ID,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["label"] is None
    assert data["country_id"] == US_COUNTRY_ID


def test_create_user_policy_policy_not_found(client):
    """Create user-policy association with non-existent policy returns 404."""
    user_id = uuid4()
    fake_policy_id = uuid4()

    response = client.post(
        "/user-policies",
        json={
            "user_id": str(user_id),
            "policy_id": str(fake_policy_id),
            "country_id": US_COUNTRY_ID,
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Policy not found"


def test_create_user_policy_duplicate_allowed(client, session, tax_benefit_model):
    """Creating duplicate user-policy association is allowed (matches FE localStorage behavior)."""
    user_id = uuid4()
    policy = create_policy(session, tax_benefit_model)
    user_policy = create_user_policy(session, user_id, policy, country_id=US_COUNTRY_ID)

    # Create duplicate - should succeed with a new ID
    response = client.post(
        "/user-policies",
        json={
            "user_id": str(user_id),
            "policy_id": str(policy.id),
            "country_id": US_COUNTRY_ID,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] != str(user_policy.id)  # New association created
    assert data["user_id"] == str(user_id)
    assert data["policy_id"] == str(policy.id)


def test_list_user_policies_with_data(
    client, session, tax_benefit_model, uk_tax_benefit_model
):
    """List user policies returns all associations for a user."""
    user_id = uuid4()
    policy1 = create_policy(session, tax_benefit_model, name="Policy 1", description="First policy")
    policy2 = create_policy(session, uk_tax_benefit_model, name="Policy 2", description="Second policy")
    create_user_policy(session, user_id, policy1, country_id=US_COUNTRY_ID, label="US policy")
    create_user_policy(session, user_id, policy2, country_id=UK_COUNTRY_ID, label="UK policy")

    response = client.get(f"/user-policies?user_id={user_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_list_user_policies_filter_by_country(
    client, session, tax_benefit_model, uk_tax_benefit_model
):
    """List user policies filtered by country_id."""
    user_id = uuid4()
    policy1 = create_policy(session, tax_benefit_model, name="Policy 1", description="First policy")
    policy2 = create_policy(session, uk_tax_benefit_model, name="Policy 2", description="Second policy")
    create_user_policy(session, user_id, policy1, country_id=US_COUNTRY_ID)
    create_user_policy(session, user_id, policy2, country_id=UK_COUNTRY_ID)

    response = client.get(
        f"/user-policies?user_id={user_id}&country_id={US_COUNTRY_ID}"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["policy_id"] == str(policy1.id)
    assert data[0]["country_id"] == US_COUNTRY_ID


def test_get_user_policy(client, session, tax_benefit_model):
    """Get a specific user-policy association by ID."""
    user_id = uuid4()
    policy = create_policy(session, tax_benefit_model)
    user_policy = create_user_policy(session, user_id, policy, country_id=US_COUNTRY_ID, label="My policy")

    response = client.get(f"/user-policies/{user_policy.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(user_policy.id)
    assert data["label"] == "My policy"
    assert data["country_id"] == US_COUNTRY_ID


def test_get_user_policy_not_found(client):
    """Get a non-existent user-policy association returns 404."""
    fake_id = uuid4()
    response = client.get(f"/user-policies/{fake_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "User-policy association not found"


def test_update_user_policy(client, session, tax_benefit_model):
    """Update a user-policy association label."""
    user_id = uuid4()
    policy = create_policy(session, tax_benefit_model)
    user_policy = create_user_policy(session, user_id, policy, country_id=US_COUNTRY_ID, label="Old label")

    response = client.patch(
        f"/user-policies/{user_policy.id}?user_id={user_id}",
        json={"label": "New label"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["label"] == "New label"
    assert data["country_id"] == US_COUNTRY_ID


def test_update_user_policy_not_found(client):
    """Update a non-existent user-policy association returns 404."""
    fake_id = uuid4()
    fake_user_id = uuid4()
    response = client.patch(
        f"/user-policies/{fake_id}?user_id={fake_user_id}",
        json={"label": "New label"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "User-policy association not found"


def test_update_user_policy_wrong_user(client, session, tax_benefit_model):
    """Update with wrong user_id returns 404 (ownership check)."""
    user_id = uuid4()
    wrong_user_id = uuid4()
    policy = create_policy(session, tax_benefit_model)
    user_policy = create_user_policy(session, user_id, policy, country_id=US_COUNTRY_ID, label="Original label")

    # Try to update with wrong user_id
    response = client.patch(
        f"/user-policies/{user_policy.id}?user_id={wrong_user_id}",
        json={"label": "Hacked label"},
    )
    assert response.status_code == 404

    # Verify original label unchanged
    response = client.get(f"/user-policies/{user_policy.id}")
    assert response.json()["label"] == "Original label"


def test_delete_user_policy(client, session, tax_benefit_model):
    """Delete a user-policy association."""
    user_id = uuid4()
    policy = create_policy(session, tax_benefit_model)
    user_policy = create_user_policy(session, user_id, policy, country_id=US_COUNTRY_ID)

    response = client.delete(f"/user-policies/{user_policy.id}?user_id={user_id}")
    assert response.status_code == 204

    # Verify it's deleted
    response = client.get(f"/user-policies/{user_policy.id}")
    assert response.status_code == 404


def test_delete_user_policy_not_found(client):
    """Delete a non-existent user-policy association returns 404."""
    fake_id = uuid4()
    fake_user_id = uuid4()
    response = client.delete(f"/user-policies/{fake_id}?user_id={fake_user_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "User-policy association not found"


def test_delete_user_policy_wrong_user(client, session, tax_benefit_model):
    """Delete with wrong user_id returns 404 (ownership check)."""
    user_id = uuid4()
    wrong_user_id = uuid4()
    policy = create_policy(session, tax_benefit_model)
    user_policy = create_user_policy(session, user_id, policy, country_id=US_COUNTRY_ID)

    # Try to delete with wrong user_id
    response = client.delete(f"/user-policies/{user_policy.id}?user_id={wrong_user_id}")
    assert response.status_code == 404

    # Verify it still exists
    response = client.get(f"/user-policies/{user_policy.id}")
    assert response.status_code == 200
