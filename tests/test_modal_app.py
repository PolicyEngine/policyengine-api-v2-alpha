"""Tests for the versioned Modal app naming."""

import os
from unittest.mock import patch

from policyengine_api.modal.app import get_app_name


class TestGetAppName:
    """Tests for app name generation."""

    def test_standard_versions(self):
        result = get_app_name("1.592.4", "2.75.1")
        assert result == "policyengine-us1-592-4-uk2-75-1"

    def test_dots_replaced_with_dashes(self):
        result = get_app_name("1.0.0", "2.0.0")
        assert "." not in result.split("policyengine-")[1]

    def test_long_versions(self):
        result = get_app_name("1.1234.56", "2.789.0")
        assert result == "policyengine-us1-1234-56-uk2-789-0"


class TestAppNameEnvOverride:
    def test_env_override_takes_precedence(self):
        with patch.dict(os.environ, {"MODAL_APP_NAME": "custom-app"}):
            result = os.environ.get(
                "MODAL_APP_NAME", get_app_name("1.0.0", "2.0.0")
            )
            assert result == "custom-app"

    def test_fallback_to_generated_name(self):
        env = os.environ.copy()
        env.pop("MODAL_APP_NAME", None)
        with patch.dict(os.environ, env, clear=True):
            result = os.environ.get(
                "MODAL_APP_NAME", get_app_name("1.592.4", "2.75.1")
            )
            assert result == "policyengine-us1-592-4-uk2-75-1"
