"""Tests for settings.database_url fallback behaviour (#277)."""

import pytest

from policyengine_api.config.settings import Settings


def test_local_default_used_when_no_override():
    s = Settings(
        supabase_url="http://localhost:54321",
        supabase_db_url="",
    )
    assert "127.0.0.1:54322" in s.database_url


def test_remote_without_db_url_raises():
    s = Settings(
        supabase_url="https://abc.supabase.co",
        supabase_db_url="",
    )
    with pytest.raises(ValueError) as exc:
        _ = s.database_url
    assert "supabase_db_url must be configured" in str(exc.value)


def test_override_used_when_provided():
    s = Settings(
        supabase_url="https://abc.supabase.co",
        supabase_db_url="postgresql://u:p@host:5432/db",
    )
    assert s.database_url == "postgresql://u:p@host:5432/db"
