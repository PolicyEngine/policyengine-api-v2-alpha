"""Tests for stored household CRUD endpoints."""

from uuid import uuid4

from test_fixtures.fixtures_households import (
    MOCK_HOUSEHOLD_MINIMAL,
    MOCK_UK_HOUSEHOLD_CREATE,
    MOCK_US_HOUSEHOLD_CREATE,
    MOCK_US_HOUSEHOLD_CREATE_LEGACY,
    MOCK_US_MULTI_GROUP_HOUSEHOLD_CREATE,
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
    assert data["household"] == [{"state_name": "CA"}]
    assert data["tax_unit"] == [{}]
    assert data["family"] == [{}]


def test_create_uk_household(client):
    """Create a UK household with benunit."""
    response = client.post("/households", json=MOCK_UK_HOUSEHOLD_CREATE)
    assert response.status_code == 201
    data = response.json()
    assert data["country_id"] == "uk"
    assert data["benunit"] == [{"is_married": False}]
    assert data["household"] == [{"region": "LONDON"}]


def test_create_household_minimal(client):
    """Create a household with minimal fields."""
    response = client.post("/households", json=MOCK_HOUSEHOLD_MINIMAL)
    assert response.status_code == 201
    data = response.json()
    assert data["label"] is None
    assert data["tax_unit"] == []
    assert data["benunit"] == []


def test_create_household_round_trips_multiple_entity_groups(client):
    """Stored household CRUD preserves multiple groups of the same type."""
    response = client.post("/households", json=MOCK_US_MULTI_GROUP_HOUSEHOLD_CREATE)
    assert response.status_code == 201
    data = response.json()
    assert len(data["tax_unit"]) == 2
    assert data["tax_unit"][0]["tax_unit_id"] == 0
    assert data["tax_unit"][1]["tax_unit_id"] == 1
    assert len(data["marital_unit"]) == 2
    assert data["people"][1]["person_marital_unit_id"] == 1


def test_create_household_invalid_country_id(client):
    """Reject invalid country_id."""
    payload = {**MOCK_HOUSEHOLD_MINIMAL, "country_id": "invalid"}
    response = client.post("/households", json=payload)
    assert response.status_code == 422


def test_create_household_accepts_legacy_singular_entity_groups(client):
    """Legacy singular entity dicts are coerced to one-element lists."""
    response = client.post("/households", json=MOCK_US_HOUSEHOLD_CREATE_LEGACY)

    assert response.status_code == 201
    data = response.json()
    assert data["tax_unit"] == [{}]
    assert data["family"] == [{}]
    assert data["household"] == [{"state_name": "CA"}]


def test_create_household_rejects_duplicate_entity_ids(client):
    """Reject duplicate entity IDs within a stored group collection."""
    payload = {
        **MOCK_US_MULTI_GROUP_HOUSEHOLD_CREATE,
        "tax_unit": [
            {"tax_unit_id": 0, "state_name": "CA"},
            {"tax_unit_id": 0, "state_name": "NY"},
        ],
    }

    response = client.post("/households", json=payload)

    assert response.status_code == 422
    assert "duplicate tax_unit_id" in response.text


def test_create_household_rejects_unknown_person_entity_links(client):
    """Reject person-to-entity references that do not resolve to stored rows."""
    payload = {
        **MOCK_US_MULTI_GROUP_HOUSEHOLD_CREATE,
        "people": [
            {
                "person_id": 0,
                "person_household_id": 0,
                "person_tax_unit_id": 7,
                "person_marital_unit_id": 0,
                "age": 30,
            }
        ],
    }

    response = client.post("/households", json=payload)

    assert response.status_code == 422
    assert "missing rows for referenced tax_unit_id values" in response.text


def test_create_household_requires_person_links_for_multi_group_rows(client):
    """Reject multi-group payloads that omit person linkage."""
    payload = {
        **MOCK_US_MULTI_GROUP_HOUSEHOLD_CREATE,
        "people": [
            {"person_id": 0, "person_household_id": 0, "age": 30},
            {"person_id": 1, "person_household_id": 0, "age": 28},
        ],
    }

    response = client.post("/households", json=payload)

    assert response.status_code == 422
    assert "people must include person_" in response.text
    assert "when " in response.text


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


def test_get_household_coerces_legacy_singular_entity_rows(client, session):
    """Legacy singular entity dicts stored in JSON are returned as one-element lists."""
    record = create_household(
        session,
        household={"state_name": "CA"},
        tax_unit={},
    )

    response = client.get(f"/households/{record.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["household"] == [{"state_name": "CA"}]
    assert data["tax_unit"] == [{}]


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
