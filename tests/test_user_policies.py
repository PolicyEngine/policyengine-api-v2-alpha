"""Tests for user-policy association endpoints.

Note: user_id is a client-generated UUID (not validated against users table),
so tests use uuid4() directly rather than creating User records.
"""

from uuid import uuid4

from policyengine_api.models import Policy, UserPolicy


def test_list_user_policies_empty(client):
    """List user policies returns empty list when user has no associations."""
    user_id = uuid4()
    response = client.get(f"/user-policies?user_id={user_id}")
    assert response.status_code == 200
    assert response.json() == []


def test_create_user_policy(client, session, tax_benefit_model):
    """Create a new user-policy association."""
    user_id = uuid4()
    policy = Policy(
        name="Test policy",
        description="A test policy",
        tax_benefit_model_id=tax_benefit_model.id,
    )
    session.add(policy)
    session.commit()
    session.refresh(policy)

    response = client.post(
        "/user-policies",
        json={
            "user_id": str(user_id),
            "policy_id": str(policy.id),
            "country_id": "us",
            "label": "My test policy",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(user_id)
    assert data["policy_id"] == str(policy.id)
    assert data["country_id"] == "us"
    assert data["label"] == "My test policy"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_user_policy_without_label(client, session, tax_benefit_model):
    """Create a user-policy association without a label."""
    user_id = uuid4()
    policy = Policy(
        name="Test policy",
        description="A test policy",
        tax_benefit_model_id=tax_benefit_model.id,
    )
    session.add(policy)
    session.commit()
    session.refresh(policy)

    response = client.post(
        "/user-policies",
        json={
            "user_id": str(user_id),
            "policy_id": str(policy.id),
            "country_id": "us",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["label"] is None
    assert data["country_id"] == "us"


def test_create_user_policy_policy_not_found(client):
    """Create user-policy association with non-existent policy returns 404."""
    user_id = uuid4()
    fake_policy_id = uuid4()

    response = client.post(
        "/user-policies",
        json={
            "user_id": str(user_id),
            "policy_id": str(fake_policy_id),
            "country_id": "us",
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Policy not found"


def test_create_user_policy_duplicate_allowed(client, session, tax_benefit_model):
    """Creating duplicate user-policy association is allowed (matches FE localStorage behavior)."""
    user_id = uuid4()
    policy = Policy(
        name="Test policy",
        description="A test policy",
        tax_benefit_model_id=tax_benefit_model.id,
    )
    session.add(policy)
    session.commit()
    session.refresh(policy)

    # Create first association
    user_policy = UserPolicy(
        user_id=user_id,
        policy_id=policy.id,
        country_id="us",
    )
    session.add(user_policy)
    session.commit()

    # Create duplicate - should succeed with a new ID
    response = client.post(
        "/user-policies",
        json={
            "user_id": str(user_id),
            "policy_id": str(policy.id),
            "country_id": "us",
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
    policy1 = Policy(
        name="Policy 1",
        description="First policy",
        tax_benefit_model_id=tax_benefit_model.id,
    )
    policy2 = Policy(
        name="Policy 2",
        description="Second policy",
        tax_benefit_model_id=uk_tax_benefit_model.id,
    )
    session.add(policy1)
    session.add(policy2)
    session.commit()
    session.refresh(policy1)
    session.refresh(policy2)

    user_policy1 = UserPolicy(
        user_id=user_id,
        policy_id=policy1.id,
        country_id="us",
        label="US policy",
    )
    user_policy2 = UserPolicy(
        user_id=user_id,
        policy_id=policy2.id,
        country_id="uk",
        label="UK policy",
    )
    session.add(user_policy1)
    session.add(user_policy2)
    session.commit()

    response = client.get(f"/user-policies?user_id={user_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_list_user_policies_filter_by_country(
    client, session, tax_benefit_model, uk_tax_benefit_model
):
    """List user policies filtered by country_id."""
    user_id = uuid4()
    policy1 = Policy(
        name="Policy 1",
        description="First policy",
        tax_benefit_model_id=tax_benefit_model.id,
    )
    policy2 = Policy(
        name="Policy 2",
        description="Second policy",
        tax_benefit_model_id=uk_tax_benefit_model.id,
    )
    session.add(policy1)
    session.add(policy2)
    session.commit()
    session.refresh(policy1)
    session.refresh(policy2)

    user_policy1 = UserPolicy(
        user_id=user_id,
        policy_id=policy1.id,
        country_id="us",
    )
    user_policy2 = UserPolicy(
        user_id=user_id,
        policy_id=policy2.id,
        country_id="uk",
    )
    session.add(user_policy1)
    session.add(user_policy2)
    session.commit()

    response = client.get(
        f"/user-policies?user_id={user_id}&country_id=us"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["policy_id"] == str(policy1.id)
    assert data[0]["country_id"] == "us"


def test_get_user_policy(client, session, tax_benefit_model):
    """Get a specific user-policy association by ID."""
    user_id = uuid4()
    policy = Policy(
        name="Test policy",
        description="A test policy",
        tax_benefit_model_id=tax_benefit_model.id,
    )
    session.add(policy)
    session.commit()
    session.refresh(policy)

    user_policy = UserPolicy(
        user_id=user_id,
        policy_id=policy.id,
        country_id="us",
        label="My policy",
    )
    session.add(user_policy)
    session.commit()
    session.refresh(user_policy)

    response = client.get(f"/user-policies/{user_policy.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(user_policy.id)
    assert data["label"] == "My policy"
    assert data["country_id"] == "us"


def test_get_user_policy_not_found(client):
    """Get a non-existent user-policy association returns 404."""
    fake_id = uuid4()
    response = client.get(f"/user-policies/{fake_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "User-policy association not found"


def test_update_user_policy(client, session, tax_benefit_model):
    """Update a user-policy association label."""
    user_id = uuid4()
    policy = Policy(
        name="Test policy",
        description="A test policy",
        tax_benefit_model_id=tax_benefit_model.id,
    )
    session.add(policy)
    session.commit()
    session.refresh(policy)

    user_policy = UserPolicy(
        user_id=user_id,
        policy_id=policy.id,
        country_id="us",
        label="Old label",
    )
    session.add(user_policy)
    session.commit()
    session.refresh(user_policy)

    response = client.patch(
        f"/user-policies/{user_policy.id}?user_id={user_id}",
        json={"label": "New label"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["label"] == "New label"
    assert data["country_id"] == "us"


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
    policy = Policy(
        name="Test policy",
        description="A test policy",
        tax_benefit_model_id=tax_benefit_model.id,
    )
    session.add(policy)
    session.commit()
    session.refresh(policy)

    user_policy = UserPolicy(
        user_id=user_id,
        policy_id=policy.id,
        country_id="us",
        label="Original label",
    )
    session.add(user_policy)
    session.commit()
    session.refresh(user_policy)

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
    policy = Policy(
        name="Test policy",
        description="A test policy",
        tax_benefit_model_id=tax_benefit_model.id,
    )
    session.add(policy)
    session.commit()
    session.refresh(policy)

    user_policy = UserPolicy(
        user_id=user_id,
        policy_id=policy.id,
        country_id="us",
    )
    session.add(user_policy)
    session.commit()
    session.refresh(user_policy)

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
    policy = Policy(
        name="Test policy",
        description="A test policy",
        tax_benefit_model_id=tax_benefit_model.id,
    )
    session.add(policy)
    session.commit()
    session.refresh(policy)

    user_policy = UserPolicy(
        user_id=user_id,
        policy_id=policy.id,
        country_id="us",
    )
    session.add(user_policy)
    session.commit()
    session.refresh(user_policy)

    # Try to delete with wrong user_id
    response = client.delete(f"/user-policies/{user_policy.id}?user_id={wrong_user_id}")
    assert response.status_code == 404

    # Verify it still exists
    response = client.get(f"/user-policies/{user_policy.id}")
    assert response.status_code == 200
