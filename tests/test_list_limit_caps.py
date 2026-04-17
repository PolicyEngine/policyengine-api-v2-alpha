"""Regression tests for the global pagination limit cap (#272).

Uses the ``client`` fixture (from ``conftest.py``) so the requests hit an
in-memory SQLite database and don't depend on Supabase.
"""


def test_parameters_rejects_over_cap_limit(client):
    resp = client.get("/parameters/", params={"limit": 501})
    assert resp.status_code == 422


def test_parameter_values_rejects_over_cap_limit(client):
    resp = client.get("/parameter-values/", params={"limit": 501})
    assert resp.status_code == 422


def test_aggregates_rejects_over_cap_limit(client):
    resp = client.get("/outputs/aggregates", params={"limit": 501})
    assert resp.status_code == 422


def test_change_aggregates_rejects_over_cap_limit(client):
    resp = client.get("/outputs/change-aggregates", params={"limit": 501})
    assert resp.status_code == 422


def test_parameters_accepts_cap_limit(client):
    # 500 is the cap itself; should be accepted (even if the DB is empty).
    resp = client.get("/parameters/", params={"limit": 500})
    assert resp.status_code == 200


def test_parameters_rejects_negative_limit(client):
    resp = client.get("/parameters/", params={"limit": 0})
    assert resp.status_code == 422
