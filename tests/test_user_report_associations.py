"""Tests for user-report association endpoints."""

from datetime import datetime, timezone
from uuid import uuid4

from test_fixtures.fixtures_user_report_associations import (
    create_report,
    create_user_report_association,
)

# ---------------------------------------------------------------------------
# POST /user-reports
# ---------------------------------------------------------------------------


def test_create_association(client, session):
    """Create an association returns 200 with id and timestamps."""
    user_id = uuid4()
    report = create_report(session)
    payload = {
        "user_id": str(user_id),
        "report_id": str(report.id),
        "country_id": "us",
        "label": "My US report",
    }
    response = client.post("/user-reports/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data
    assert data["user_id"] == str(user_id)
    assert data["report_id"] == str(report.id)
    assert data["country_id"] == "us"
    assert data["label"] == "My US report"
    assert data["last_run_at"] is None


def test_create_association_with_last_run_at(client, session):
    """Create an association with last_run_at set."""
    user_id = uuid4()
    report = create_report(session)
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "user_id": str(user_id),
        "report_id": str(report.id),
        "country_id": "us",
        "last_run_at": now,
    }
    response = client.post("/user-reports/", json=payload)
    assert response.status_code == 200
    assert response.json()["last_run_at"] is not None


def test_create_association_report_not_found(client):
    """Creating with a non-existent report returns 404."""
    payload = {
        "user_id": str(uuid4()),
        "report_id": str(uuid4()),
        "country_id": "us",
    }
    response = client.post("/user-reports/", json=payload)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_create_association_invalid_country(client, session):
    """Creating with an invalid country_id returns 422."""
    report = create_report(session)
    payload = {
        "user_id": str(uuid4()),
        "report_id": str(report.id),
        "country_id": "invalid",
    }
    response = client.post("/user-reports/", json=payload)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /user-reports/?user_id=...
# ---------------------------------------------------------------------------


def test_list_by_user_empty(client):
    """List associations for a user with none returns empty list."""
    response = client.get("/user-reports/", params={"user_id": str(uuid4())})
    assert response.status_code == 200
    assert response.json() == []


def test_list_by_user(client, session):
    """List all associations for a user."""
    user_id = uuid4()
    r1 = create_report(session)
    r2 = create_report(session)
    create_user_report_association(session, user_id, r1, label="First")
    create_user_report_association(session, user_id, r2, label="Second")

    response = client.get("/user-reports/", params={"user_id": str(user_id)})
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_by_user_filter_country(client, session):
    """Filter associations by country_id."""
    user_id = uuid4()
    report = create_report(session)
    create_user_report_association(session, user_id, report, country_id="us")
    create_user_report_association(session, user_id, report, country_id="uk")

    response = client.get(
        "/user-reports/",
        params={"user_id": str(user_id), "country_id": "uk"},
    )
    data = response.json()
    assert len(data) == 1
    assert data[0]["country_id"] == "uk"


# ---------------------------------------------------------------------------
# GET /user-reports/{id}
# ---------------------------------------------------------------------------


def test_get_by_id(client, session):
    """Get a specific association by ID."""
    user_id = uuid4()
    report = create_report(session)
    assoc = create_user_report_association(
        session, user_id, report, label="Test"
    )

    response = client.get(f"/user-reports/{assoc.id}")
    assert response.status_code == 200
    assert response.json()["id"] == str(assoc.id)
    assert response.json()["label"] == "Test"


def test_get_by_id_not_found(client):
    """Get a non-existent association returns 404."""
    response = client.get(f"/user-reports/{uuid4()}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /user-reports/{id}?user_id=...
# ---------------------------------------------------------------------------


def test_update_label(client, session):
    """Update label via PATCH."""
    user_id = uuid4()
    report = create_report(session)
    assoc = create_user_report_association(
        session, user_id, report, label="Old"
    )

    response = client.patch(
        f"/user-reports/{assoc.id}",
        json={"label": "New label"},
        params={"user_id": str(user_id)},
    )
    assert response.status_code == 200
    assert response.json()["label"] == "New label"


def test_update_last_run_at(client, session):
    """Update last_run_at via PATCH."""
    user_id = uuid4()
    report = create_report(session)
    assoc = create_user_report_association(session, user_id, report)

    now = datetime.now(timezone.utc).isoformat()
    response = client.patch(
        f"/user-reports/{assoc.id}",
        json={"last_run_at": now},
        params={"user_id": str(user_id)},
    )
    assert response.status_code == 200
    assert response.json()["last_run_at"] is not None


def test_update_wrong_user(client, session):
    """Update with wrong user_id returns 404."""
    user_id = uuid4()
    report = create_report(session)
    assoc = create_user_report_association(
        session, user_id, report, label="Mine"
    )

    response = client.patch(
        f"/user-reports/{assoc.id}",
        json={"label": "Stolen"},
        params={"user_id": str(uuid4())},
    )
    assert response.status_code == 404


def test_update_not_found(client):
    """Update a non-existent association returns 404."""
    response = client.patch(
        f"/user-reports/{uuid4()}",
        json={"label": "Something"},
        params={"user_id": str(uuid4())},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /user-reports/{id}?user_id=...
# ---------------------------------------------------------------------------


def test_delete_association(client, session):
    """Delete an association returns 204."""
    user_id = uuid4()
    report = create_report(session)
    assoc = create_user_report_association(session, user_id, report)

    response = client.delete(
        f"/user-reports/{assoc.id}",
        params={"user_id": str(user_id)},
    )
    assert response.status_code == 204

    # Confirm it's gone
    response = client.get(f"/user-reports/{assoc.id}")
    assert response.status_code == 404


def test_delete_wrong_user(client, session):
    """Delete with wrong user_id returns 404."""
    user_id = uuid4()
    report = create_report(session)
    assoc = create_user_report_association(session, user_id, report)

    response = client.delete(
        f"/user-reports/{assoc.id}",
        params={"user_id": str(uuid4())},
    )
    assert response.status_code == 404


def test_delete_not_found(client):
    """Delete a non-existent association returns 404."""
    response = client.delete(
        f"/user-reports/{uuid4()}",
        params={"user_id": str(uuid4())},
    )
    assert response.status_code == 404
