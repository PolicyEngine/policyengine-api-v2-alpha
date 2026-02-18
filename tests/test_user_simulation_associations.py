"""Tests for user-simulation association endpoints."""

from uuid import uuid4

from test_fixtures.fixtures_user_simulation_associations import (
    create_simulation,
    create_user_simulation_association,
)

# ---------------------------------------------------------------------------
# POST /user-simulations
# ---------------------------------------------------------------------------


def test_create_association(client, session):
    """Create an association returns 200 with id and timestamps."""
    user_id = uuid4()
    simulation = create_simulation(session)
    payload = {
        "user_id": str(user_id),
        "simulation_id": str(simulation.id),
        "country_id": "us",
        "label": "My US simulation",
    }
    response = client.post("/user-simulations/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data
    assert data["user_id"] == str(user_id)
    assert data["simulation_id"] == str(simulation.id)
    assert data["country_id"] == "us"
    assert data["label"] == "My US simulation"


def test_create_association_allows_duplicates(client, session):
    """Multiple associations to the same simulation are allowed."""
    user_id = uuid4()
    simulation = create_simulation(session)
    payload = {
        "user_id": str(user_id),
        "simulation_id": str(simulation.id),
        "country_id": "us",
        "label": "First label",
    }
    r1 = client.post("/user-simulations/", json=payload)
    assert r1.status_code == 200

    payload["label"] = "Second label"
    r2 = client.post("/user-simulations/", json=payload)
    assert r2.status_code == 200
    assert r1.json()["id"] != r2.json()["id"]


def test_create_association_simulation_not_found(client):
    """Creating with a non-existent simulation returns 404."""
    payload = {
        "user_id": str(uuid4()),
        "simulation_id": str(uuid4()),
        "country_id": "us",
    }
    response = client.post("/user-simulations/", json=payload)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_create_association_invalid_country(client, session):
    """Creating with an invalid country_id returns 422."""
    simulation = create_simulation(session)
    payload = {
        "user_id": str(uuid4()),
        "simulation_id": str(simulation.id),
        "country_id": "invalid",
    }
    response = client.post("/user-simulations/", json=payload)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /user-simulations/?user_id=...
# ---------------------------------------------------------------------------


def test_list_by_user_empty(client):
    """List associations for a user with none returns empty list."""
    response = client.get(
        "/user-simulations/", params={"user_id": str(uuid4())}
    )
    assert response.status_code == 200
    assert response.json() == []


def test_list_by_user(client, session):
    """List all associations for a user."""
    user_id = uuid4()
    sim1 = create_simulation(session)
    sim2 = create_simulation(session)
    create_user_simulation_association(session, user_id, sim1, label="First")
    create_user_simulation_association(session, user_id, sim2, label="Second")

    response = client.get(
        "/user-simulations/", params={"user_id": str(user_id)}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_list_by_user_filter_country(client, session):
    """Filter associations by country_id."""
    user_id = uuid4()
    simulation = create_simulation(session)
    create_user_simulation_association(
        session, user_id, simulation, country_id="us"
    )
    create_user_simulation_association(
        session, user_id, simulation, country_id="uk"
    )

    response = client.get(
        "/user-simulations/",
        params={"user_id": str(user_id), "country_id": "uk"},
    )
    data = response.json()
    assert len(data) == 1
    assert data[0]["country_id"] == "uk"


# ---------------------------------------------------------------------------
# GET /user-simulations/{id}
# ---------------------------------------------------------------------------


def test_get_by_id(client, session):
    """Get a specific association by ID."""
    user_id = uuid4()
    simulation = create_simulation(session)
    assoc = create_user_simulation_association(
        session, user_id, simulation, label="Test"
    )

    response = client.get(f"/user-simulations/{assoc.id}")
    assert response.status_code == 200
    assert response.json()["id"] == str(assoc.id)
    assert response.json()["label"] == "Test"


def test_get_by_id_not_found(client):
    """Get a non-existent association returns 404."""
    response = client.get(f"/user-simulations/{uuid4()}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /user-simulations/{id}?user_id=...
# ---------------------------------------------------------------------------


def test_update_label(client, session):
    """Update label via PATCH."""
    user_id = uuid4()
    simulation = create_simulation(session)
    assoc = create_user_simulation_association(
        session, user_id, simulation, label="Old"
    )

    response = client.patch(
        f"/user-simulations/{assoc.id}",
        json={"label": "New label"},
        params={"user_id": str(user_id)},
    )
    assert response.status_code == 200
    assert response.json()["label"] == "New label"


def test_update_wrong_user(client, session):
    """Update with wrong user_id returns 404."""
    user_id = uuid4()
    simulation = create_simulation(session)
    assoc = create_user_simulation_association(
        session, user_id, simulation, label="Mine"
    )

    response = client.patch(
        f"/user-simulations/{assoc.id}",
        json={"label": "Stolen"},
        params={"user_id": str(uuid4())},
    )
    assert response.status_code == 404


def test_update_not_found(client):
    """Update a non-existent association returns 404."""
    response = client.patch(
        f"/user-simulations/{uuid4()}",
        json={"label": "Something"},
        params={"user_id": str(uuid4())},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /user-simulations/{id}?user_id=...
# ---------------------------------------------------------------------------


def test_delete_association(client, session):
    """Delete an association returns 204."""
    user_id = uuid4()
    simulation = create_simulation(session)
    assoc = create_user_simulation_association(session, user_id, simulation)

    response = client.delete(
        f"/user-simulations/{assoc.id}",
        params={"user_id": str(user_id)},
    )
    assert response.status_code == 204

    # Confirm it's gone
    response = client.get(f"/user-simulations/{assoc.id}")
    assert response.status_code == 404


def test_delete_wrong_user(client, session):
    """Delete with wrong user_id returns 404."""
    user_id = uuid4()
    simulation = create_simulation(session)
    assoc = create_user_simulation_association(session, user_id, simulation)

    response = client.delete(
        f"/user-simulations/{assoc.id}",
        params={"user_id": str(uuid4())},
    )
    assert response.status_code == 404


def test_delete_not_found(client):
    """Delete a non-existent association returns 404."""
    response = client.delete(
        f"/user-simulations/{uuid4()}",
        params={"user_id": str(uuid4())},
    )
    assert response.status_code == 404
