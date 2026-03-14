"""Tests for stored household CRUD endpoints."""

from uuid import uuid4

from test_fixtures.fixtures_households import (
    MOCK_HOUSEHOLD_MINIMAL,
    MOCK_UK_HOUSEHOLD_CREATE,
    MOCK_US_HOUSEHOLD_CREATE,
    create_household,
)

# ---------------------------------------------------------------------------
# POST /households
# ---------------------------------------------------------------------------


def test_create_us_household(client):
    """Create a US household returns 201 with id and timestamps."""
    response = client.post("/households", json=MOCK_US_HOUSEHOLD_CREATE)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data
    assert data["country_id"] == "us"
    assert data["year"] == 2024
    assert data["label"] == "US test household"


def test_create_household_returns_people_and_entities(client):
    """Created household response includes people and entity groups."""
    response = client.post("/households", json=MOCK_US_HOUSEHOLD_CREATE)
    data = response.json()
    assert len(data["people"]) == 2
    assert data["people"][0]["age"] == 30
    assert data["people"][0]["employment_income"] == 50000
    assert data["household"] == {"state_name": "CA"}
    assert data["tax_unit"] == {}
    assert data["family"] == {}


def test_create_uk_household(client):
    """Create a UK household with benunit."""
    response = client.post("/households", json=MOCK_UK_HOUSEHOLD_CREATE)
    assert response.status_code == 201
    data = response.json()
    assert data["country_id"] == "uk"
    assert data["benunit"] == {"is_married": False}
    assert data["household"] == {"region": "LONDON"}


def test_create_household_minimal(client):
    """Create a household with minimal fields."""
    response = client.post("/households", json=MOCK_HOUSEHOLD_MINIMAL)
    assert response.status_code == 201
    data = response.json()
    assert data["label"] is None
    assert data["tax_unit"] is None
    assert data["benunit"] is None


def test_create_household_invalid_country_id(client):
    """Reject invalid country_id."""
    payload = {**MOCK_HOUSEHOLD_MINIMAL, "country_id": "invalid"}
    response = client.post("/households", json=payload)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /households/{id}
# ---------------------------------------------------------------------------


def test_get_household(client, session):
    """Get a stored household by ID."""
    record = create_household(session)
    response = client.get(f"/households/{record.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(record.id)
    assert data["country_id"] == "us"


def test_get_household_not_found(client):
    """Get a non-existent household returns 404."""
    fake_id = uuid4()
    response = client.get(f"/households/{fake_id}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


# ---------------------------------------------------------------------------
# GET /households
# ---------------------------------------------------------------------------


def test_list_households_empty(client):
    """List households returns empty list when none exist."""
    response = client.get("/households")
    assert response.status_code == 200
    assert response.json() == []


def test_list_households_with_data(client, session):
    """List households returns all stored households."""
    create_household(session, label="first")
    create_household(session, label="second")
    response = client.get("/households")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_list_households_filter_by_country_id(client, session):
    """Filter households by country_id."""
    create_household(session, country_id="us")
    create_household(session, country_id="uk")
    response = client.get("/households", params={"country_id": "uk"})
    data = response.json()
    assert len(data) == 1
    assert data[0]["country_id"] == "uk"


def test_list_households_limit_and_offset(client, session):
    """Respect limit and offset pagination."""
    for i in range(5):
        create_household(session, label=f"household-{i}")
    response = client.get("/households", params={"limit": 2, "offset": 1})
    data = response.json()
    assert len(data) == 2


# ---------------------------------------------------------------------------
# DELETE /households/{id}
# ---------------------------------------------------------------------------


def test_delete_household(client, session):
    """Delete a household returns 204."""
    record = create_household(session)
    response = client.delete(f"/households/{record.id}")
    assert response.status_code == 204

    # Confirm it's gone
    response = client.get(f"/households/{record.id}")
    assert response.status_code == 404


def test_delete_household_not_found(client):
    """Delete a non-existent household returns 404."""
    fake_id = uuid4()
    response = client.delete(f"/households/{fake_id}")
    assert response.status_code == 404
