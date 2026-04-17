"""Auth tests for the destructive /analysis/rerun/{report_id} endpoint (#267)."""

from fastapi.testclient import TestClient

from policyengine_api.config.settings import settings
from policyengine_api.main import app

client = TestClient(app)


def test_rerun_requires_api_key(monkeypatch):
    """Without an API key the endpoint must reject the request."""
    monkeypatch.setattr(settings, "api_key", "secret-value")
    resp = client.post("/analysis/rerun/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 401


def test_rerun_rejects_wrong_key(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "secret-value")
    resp = client.post(
        "/analysis/rerun/00000000-0000-0000-0000-000000000000",
        headers={"X-API-Key": "not-the-secret"},
    )
    assert resp.status_code == 401


def test_rerun_returns_503_when_unconfigured(monkeypatch):
    """If the server has no key configured we must not silently accept."""
    monkeypatch.setattr(settings, "api_key", "")
    resp = client.post(
        "/analysis/rerun/00000000-0000-0000-0000-000000000000",
        headers={"X-API-Key": "anything"},
    )
    assert resp.status_code == 503
