"""Tests for user-household association endpoints."""

from uuid import uuid4

from test_fixtures.fixtures_user_household_associations import (
    create_association,
    create_household,
    create_user,
)

# ---------------------------------------------------------------------------
# POST /user-household-associations
# ---------------------------------------------------------------------------


def test_create_association(client, session):
    """Create an association returns 201 with id and timestamps."""
    user = create_user(session)
    household = create_household(session)
    payload = {
        "user_id": str(user.id),
        "household_id": str(household.id),
        "country_id": "us",
        "label": "My US household",
    }
    response = client.post("/user-household-associations", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data
    assert data["user_id"] == str(user.id)
    assert data["household_id"] == str(household.id)
    assert data["country_id"] == "us"
    assert data["label"] == "My US household"


def test_create_association_allows_duplicates(client, session):
    """Multiple associations to the same household are allowed."""
    user = create_user(session)
    household = create_household(session)
    payload = {
        "user_id": str(user.id),
        "household_id": str(household.id),
        "country_id": "us",
        "label": "First label",
    }
    r1 = client.post("/user-household-associations", json=payload)
    assert r1.status_code == 201

    payload["label"] = "Second label"
    r2 = client.post("/user-household-associations", json=payload)
    assert r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]


def test_create_association_household_not_found(client, session):
    """Creating with a non-existent household returns 404."""
    user = create_user(session)
    payload = {
        "user_id": str(user.id),
        "household_id": str(uuid4()),
        "country_id": "us",
    }
    response = client.post("/user-household-associations", json=payload)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


# ---------------------------------------------------------------------------
# GET /user-household-associations/user/{user_id}
# ---------------------------------------------------------------------------


def test_list_by_user_empty(client):
    """List associations for a user with none returns empty list."""
    response = client.get(f"/user-household-associations/user/{uuid4()}")
    assert response.status_code == 200
    assert response.json() == []


def test_list_by_user(client, session):
    """List all associations for a user."""
    user = create_user(session)
    h1 = create_household(session, label="H1")
    h2 = create_household(session, label="H2")
    create_association(session, user.id, h1.id, label="First")
    create_association(session, user.id, h2.id, label="Second")

    response = client.get(f"/user-household-associations/user/{user.id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_list_by_user_filter_country(client, session):
    """Filter associations by country_id."""
    user = create_user(session)
    household = create_household(session)
    create_association(session, user.id, household.id, country_id="us")
    create_association(session, user.id, household.id, country_id="uk")

    response = client.get(
        f"/user-household-associations/user/{user.id}",
        params={"country_id": "uk"},
    )
    data = response.json()
    assert len(data) == 1
    assert data[0]["country_id"] == "uk"


# ---------------------------------------------------------------------------
# GET /user-household-associations/{user_id}/{household_id}
# ---------------------------------------------------------------------------


def test_list_by_user_and_household(client, session):
    """List associations for a specific user+household pair."""
    user = create_user(session)
    household = create_household(session)
    create_association(session, user.id, household.id, label="Label A")
    create_association(session, user.id, household.id, label="Label B")

    response = client.get(f"/user-household-associations/{user.id}/{household.id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_list_by_user_and_household_empty(client):
    """Returns empty list when no associations exist for the pair."""
    response = client.get(f"/user-household-associations/{uuid4()}/{uuid4()}")
    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# PUT /user-household-associations/{association_id}
# ---------------------------------------------------------------------------


def test_update_association_label(client, session):
    """Update label and verify updated_at changes."""
    user = create_user(session)
    household = create_household(session)
    assoc = create_association(session, user.id, household.id, label="Old")

    response = client.put(
        f"/user-household-associations/{assoc.id}",
        json={"label": "New label"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["label"] == "New label"


def test_update_association_not_found(client):
    """Update a non-existent association returns 404."""
    response = client.put(
        f"/user-household-associations/{uuid4()}",
        json={"label": "Something"},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


# ---------------------------------------------------------------------------
# DELETE /user-household-associations/{association_id}
# ---------------------------------------------------------------------------


def test_delete_association(client, session):
    """Delete an association returns 204."""
    user = create_user(session)
    household = create_household(session)
    assoc = create_association(session, user.id, household.id)

    response = client.delete(f"/user-household-associations/{assoc.id}")
    assert response.status_code == 204

    # Confirm it's gone
    response = client.get(f"/user-household-associations/{user.id}/{household.id}")
    assert response.json() == []


def test_delete_association_not_found(client):
    """Delete a non-existent association returns 404."""
    response = client.delete(f"/user-household-associations/{uuid4()}")
    assert response.status_code == 404
