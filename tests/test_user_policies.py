"""Tests for user-policy association endpoints."""

from uuid import uuid4

from policyengine_api.models import Policy, User, UserPolicy


def test_list_user_policies_empty(client, session):
    """List user policies returns empty list when user has no associations."""
    user = User(first_name="Test", last_name="User", email="test@example.com")
    session.add(user)
    session.commit()

    response = client.get(f"/user-policies?user_id={user.id}")
    assert response.status_code == 200
    assert response.json() == []


def test_create_user_policy(client, session, tax_benefit_model):
    """Create a new user-policy association."""
    user = User(first_name="Test", last_name="User", email="test@example.com")
    policy = Policy(
        name="Test policy",
        description="A test policy",
        tax_benefit_model_id=tax_benefit_model.id,
    )
    session.add(user)
    session.add(policy)
    session.commit()
    session.refresh(user)
    session.refresh(policy)

    response = client.post(
        "/user-policies",
        json={
            "user_id": str(user.id),
            "policy_id": str(policy.id),
            "label": "My test policy",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(user.id)
    assert data["policy_id"] == str(policy.id)
    assert data["label"] == "My test policy"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_user_policy_without_label(client, session, tax_benefit_model):
    """Create a user-policy association without a label."""
    user = User(first_name="Test", last_name="User", email="test@example.com")
    policy = Policy(
        name="Test policy",
        description="A test policy",
        tax_benefit_model_id=tax_benefit_model.id,
    )
    session.add(user)
    session.add(policy)
    session.commit()
    session.refresh(user)
    session.refresh(policy)

    response = client.post(
        "/user-policies",
        json={
            "user_id": str(user.id),
            "policy_id": str(policy.id),
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["label"] is None


def test_create_user_policy_user_not_found(client):
    """Create user-policy association with non-existent user returns 404."""
    fake_user_id = uuid4()
    fake_policy_id = uuid4()

    response = client.post(
        "/user-policies",
        json={
            "user_id": str(fake_user_id),
            "policy_id": str(fake_policy_id),
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_create_user_policy_policy_not_found(client, session):
    """Create user-policy association with non-existent policy returns 404."""
    user = User(first_name="Test", last_name="User", email="test@example.com")
    session.add(user)
    session.commit()
    session.refresh(user)

    fake_policy_id = uuid4()
    response = client.post(
        "/user-policies",
        json={
            "user_id": str(user.id),
            "policy_id": str(fake_policy_id),
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Policy not found"


def test_create_user_policy_duplicate(client, session, tax_benefit_model):
    """Creating duplicate user-policy association returns 409."""
    user = User(first_name="Test", last_name="User", email="test@example.com")
    policy = Policy(
        name="Test policy",
        description="A test policy",
        tax_benefit_model_id=tax_benefit_model.id,
    )
    session.add(user)
    session.add(policy)
    session.commit()
    session.refresh(user)
    session.refresh(policy)

    # Create first association
    user_policy = UserPolicy(
        user_id=user.id,
        policy_id=policy.id,
    )
    session.add(user_policy)
    session.commit()

    # Try to create duplicate
    response = client.post(
        "/user-policies",
        json={
            "user_id": str(user.id),
            "policy_id": str(policy.id),
        },
    )
    assert response.status_code == 409
    assert "already has an association" in response.json()["detail"]


def test_list_user_policies_with_data(client, session, tax_benefit_model, uk_tax_benefit_model):
    """List user policies returns all associations for a user."""
    user = User(first_name="Test", last_name="User", email="test@example.com")
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
    session.add(user)
    session.add(policy1)
    session.add(policy2)
    session.commit()
    session.refresh(user)
    session.refresh(policy1)
    session.refresh(policy2)

    user_policy1 = UserPolicy(
        user_id=user.id,
        policy_id=policy1.id,
        label="US policy",
    )
    user_policy2 = UserPolicy(
        user_id=user.id,
        policy_id=policy2.id,
        label="UK policy",
    )
    session.add(user_policy1)
    session.add(user_policy2)
    session.commit()

    response = client.get(f"/user-policies?user_id={user.id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_list_user_policies_filter_by_tax_benefit_model(
    client, session, tax_benefit_model, uk_tax_benefit_model
):
    """List user policies filtered by tax_benefit_model_id via Policy join."""
    user = User(first_name="Test", last_name="User", email="test@example.com")
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
    session.add(user)
    session.add(policy1)
    session.add(policy2)
    session.commit()
    session.refresh(user)
    session.refresh(policy1)
    session.refresh(policy2)

    user_policy1 = UserPolicy(
        user_id=user.id,
        policy_id=policy1.id,
    )
    user_policy2 = UserPolicy(
        user_id=user.id,
        policy_id=policy2.id,
    )
    session.add(user_policy1)
    session.add(user_policy2)
    session.commit()

    response = client.get(
        f"/user-policies?user_id={user.id}&tax_benefit_model_id={tax_benefit_model.id}"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["policy_id"] == str(policy1.id)


def test_get_user_policy(client, session, tax_benefit_model):
    """Get a specific user-policy association by ID."""
    user = User(first_name="Test", last_name="User", email="test@example.com")
    policy = Policy(
        name="Test policy",
        description="A test policy",
        tax_benefit_model_id=tax_benefit_model.id,
    )
    session.add(user)
    session.add(policy)
    session.commit()
    session.refresh(user)
    session.refresh(policy)

    user_policy = UserPolicy(
        user_id=user.id,
        policy_id=policy.id,
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


def test_get_user_policy_not_found(client):
    """Get a non-existent user-policy association returns 404."""
    fake_id = uuid4()
    response = client.get(f"/user-policies/{fake_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "User-policy association not found"


def test_update_user_policy(client, session, tax_benefit_model):
    """Update a user-policy association label."""
    user = User(first_name="Test", last_name="User", email="test@example.com")
    policy = Policy(
        name="Test policy",
        description="A test policy",
        tax_benefit_model_id=tax_benefit_model.id,
    )
    session.add(user)
    session.add(policy)
    session.commit()
    session.refresh(user)
    session.refresh(policy)

    user_policy = UserPolicy(
        user_id=user.id,
        policy_id=policy.id,
        label="Old label",
    )
    session.add(user_policy)
    session.commit()
    session.refresh(user_policy)

    response = client.patch(
        f"/user-policies/{user_policy.id}",
        json={"label": "New label"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["label"] == "New label"


def test_update_user_policy_not_found(client):
    """Update a non-existent user-policy association returns 404."""
    fake_id = uuid4()
    response = client.patch(
        f"/user-policies/{fake_id}",
        json={"label": "New label"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "User-policy association not found"


def test_delete_user_policy(client, session, tax_benefit_model):
    """Delete a user-policy association."""
    user = User(first_name="Test", last_name="User", email="test@example.com")
    policy = Policy(
        name="Test policy",
        description="A test policy",
        tax_benefit_model_id=tax_benefit_model.id,
    )
    session.add(user)
    session.add(policy)
    session.commit()
    session.refresh(user)
    session.refresh(policy)

    user_policy = UserPolicy(
        user_id=user.id,
        policy_id=policy.id,
    )
    session.add(user_policy)
    session.commit()
    session.refresh(user_policy)

    response = client.delete(f"/user-policies/{user_policy.id}")
    assert response.status_code == 204

    # Verify it's deleted
    response = client.get(f"/user-policies/{user_policy.id}")
    assert response.status_code == 404


def test_delete_user_policy_not_found(client):
    """Delete a non-existent user-policy association returns 404."""
    fake_id = uuid4()
    response = client.delete(f"/user-policies/{fake_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "User-policy association not found"
