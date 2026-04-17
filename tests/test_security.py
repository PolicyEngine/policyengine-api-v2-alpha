"""Tests for security helpers (HMAC call IDs and API key gating)."""

import pytest
from fastapi import HTTPException

from policyengine_api import security
from policyengine_api.config.settings import settings


class TestSignedCallId:
    def test_round_trip_valid(self):
        call_id = security.issue_signed_call_id()
        # Shape: "fc-<24hex>.<tag>"
        assert call_id.startswith("fc-")
        assert "." in call_id
        assert security.verify_signed_call_id(call_id) == call_id

    def test_tampered_raw_id_rejected(self):
        call_id = security.issue_signed_call_id()
        raw, _, tag = call_id.rpartition(".")
        tampered = f"{raw}x.{tag}"
        with pytest.raises(HTTPException) as exc:
            security.verify_signed_call_id(tampered)
        assert exc.value.status_code == 401

    def test_missing_separator_rejected(self):
        with pytest.raises(HTTPException) as exc:
            security.verify_signed_call_id("fc-nohmac")
        assert exc.value.status_code == 401

    def test_empty_tag_rejected(self):
        with pytest.raises(HTTPException):
            security.verify_signed_call_id("fc-abc.")

    def test_non_string_rejected(self):
        with pytest.raises(HTTPException):
            security.verify_signed_call_id(None)  # type: ignore[arg-type]


class TestApiKey:
    def test_requires_configured_key(self, monkeypatch):
        monkeypatch.setattr(settings, "api_key", "")
        with pytest.raises(HTTPException) as exc:
            security.require_api_key(x_api_key="something")
        assert exc.value.status_code == 503

    def test_rejects_missing_key(self, monkeypatch):
        monkeypatch.setattr(settings, "api_key", "correct-horse")
        with pytest.raises(HTTPException) as exc:
            security.require_api_key(x_api_key=None)
        assert exc.value.status_code == 401

    def test_rejects_wrong_key(self, monkeypatch):
        monkeypatch.setattr(settings, "api_key", "correct-horse")
        with pytest.raises(HTTPException) as exc:
            security.require_api_key(x_api_key="battery-staple")
        assert exc.value.status_code == 401

    def test_accepts_matching_key(self, monkeypatch):
        monkeypatch.setattr(settings, "api_key", "correct-horse")
        # Should not raise
        security.require_api_key(x_api_key="correct-horse")
