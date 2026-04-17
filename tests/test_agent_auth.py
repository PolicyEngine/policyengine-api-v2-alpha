"""Unit tests for agent callback authentication (#265).

These tests run without external services — they only exercise the HMAC
verification on the ``/agent/log/{call_id}`` and ``/agent/complete/{call_id}``
endpoints.
"""

from fastapi.testclient import TestClient

from policyengine_api import security
from policyengine_api.api import agent as agent_router
from policyengine_api.main import app

client = TestClient(app)


def test_log_rejects_unsigned_call_id():
    """Unsigned (attacker-supplied) call IDs must be rejected."""
    resp = client.post(
        "/agent/log/fc-this-is-not-signed",
        json={"message": "pwn"},
    )
    assert resp.status_code == 401


def test_complete_rejects_unsigned_call_id():
    resp = client.post(
        "/agent/complete/fc-this-is-not-signed",
        json={"status": "failed"},
    )
    assert resp.status_code == 401


def test_complete_rejects_tampered_signature():
    signed = security.issue_signed_call_id()
    raw, _, tag = signed.rpartition(".")
    bad = f"{raw}.{'0' * len(tag)}"
    resp = client.post(f"/agent/complete/{bad}", json={"status": "ok"})
    assert resp.status_code == 401


def test_log_accepts_valid_signed_id():
    signed = security.issue_signed_call_id()
    # Seed the call entry so the handler accepts the log (cache is TTL-bounded).
    agent_router._calls[signed] = {
        "status": "running",
        "result": None,
    }
    resp = client.post(f"/agent/log/{signed}", json={"message": "hi"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    # Verify the log was actually recorded.
    assert len(agent_router._logs[signed]) == 1
    assert agent_router._logs[signed][0].message == "hi"


def test_call_cache_is_bounded():
    """Ensure the in-memory stores are bounded TTLCaches rather than dicts."""
    from cachetools import TTLCache

    assert isinstance(agent_router._calls, TTLCache)
    assert isinstance(agent_router._logs, TTLCache)
    # Cap configured in module; sanity check it is small relative to memory.
    assert agent_router._calls.maxsize <= 10_000
