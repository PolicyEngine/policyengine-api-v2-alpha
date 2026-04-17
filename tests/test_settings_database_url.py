"""Tests for settings.database_url fallback behaviour (#277).

``tests/test_seed_utils.py`` monkey-patches ``sys.modules`` with a MagicMock
for ``policyengine_api.config.settings``; if pytest loads that file first the
real ``Settings`` class is no longer importable under its canonical name. We
restore the real module before exercising the real behaviour.
"""

import importlib
import sys

import pytest


@pytest.fixture(autouse=True)
def _real_settings_module():
    """Ensure the real settings module is loaded for these tests."""
    stashed = {
        name: sys.modules.pop(name, None)
        for name in (
            "policyengine_api.config",
            "policyengine_api.config.settings",
        )
    }
    # Re-import to pick up the real module (not a MagicMock left behind by
    # test_seed_utils.py).
    importlib.import_module("policyengine_api.config")
    importlib.import_module("policyengine_api.config.settings")
    try:
        yield
    finally:
        for name, mod in stashed.items():
            if mod is not None:
                sys.modules[name] = mod


def test_local_default_used_when_no_override():
    from policyengine_api.config.settings import Settings

    s = Settings(
        supabase_url="http://localhost:54321",
        supabase_db_url="",
    )
    assert "127.0.0.1:54322" in s.database_url


def test_remote_without_db_url_raises():
    from policyengine_api.config.settings import Settings

    s = Settings(
        supabase_url="https://abc.supabase.co",
        supabase_db_url="",
    )
    with pytest.raises(ValueError) as exc:
        _ = s.database_url
    assert "supabase_db_url must be configured" in str(exc.value)


def test_override_used_when_provided():
    from policyengine_api.config.settings import Settings

    s = Settings(
        supabase_url="https://abc.supabase.co",
        supabase_db_url="postgresql://u:p@host:5432/db",
    )
    assert s.database_url == "postgresql://u:p@host:5432/db"
