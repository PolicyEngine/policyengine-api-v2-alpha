"""Tests for version_resolver module."""

from unittest.mock import MagicMock, patch

import pytest

from policyengine_api.version_resolver import (
    _resolve_app_name,
    resolve_modal_function,
)


@pytest.fixture(autouse=True)
def clear_lru_cache():
    """Clear the LRU cache between tests."""
    _resolve_app_name.cache_clear()
    yield
    _resolve_app_name.cache_clear()


class TestResolveAppName:
    """Tests for _resolve_app_name (internal resolution logic)."""

    def test_resolves_latest_version(self):
        """version=None resolves 'latest' key then looks up app name."""
        mock_dict = MagicMock()
        mock_dict.__getitem__ = MagicMock(
            side_effect=lambda key: {
                "latest": "1.592.4",
                "1.592.4": "policyengine-v2-us1-592-4-uk2-75-1",
            }[key]
        )

        with patch("modal.Dict.from_name", return_value=mock_dict):
            result = _resolve_app_name("us", None, "main")

        assert result == "policyengine-v2-us1-592-4-uk2-75-1"

    def test_resolves_specific_version(self):
        """Specific version string resolves directly to app name."""
        mock_dict = MagicMock()
        mock_dict.__getitem__ = MagicMock(
            return_value="policyengine-v2-us1-459-0-uk2-65-9"
        )

        with patch("modal.Dict.from_name", return_value=mock_dict):
            result = _resolve_app_name("us", "1.459.0", "staging")

        assert result == "policyengine-v2-us1-459-0-uk2-65-9"
        mock_dict.__getitem__.assert_called_once_with("1.459.0")

    def test_routes_to_correct_dict_for_us(self):
        """Country 'us' reads from simulation-api-us-versions."""
        mock_dict = MagicMock()
        mock_dict.__getitem__ = MagicMock(return_value="app-name")

        with patch("modal.Dict.from_name", return_value=mock_dict) as from_name:
            _resolve_app_name("us", "1.0.0", "main")

        from_name.assert_called_once_with(
            "simulation-api-us-versions", environment_name="main"
        )

    def test_routes_to_correct_dict_for_uk(self):
        """Country 'uk' reads from simulation-api-uk-versions."""
        mock_dict = MagicMock()
        mock_dict.__getitem__ = MagicMock(return_value="app-name")

        with patch("modal.Dict.from_name", return_value=mock_dict) as from_name:
            _resolve_app_name("uk", "2.0.0", "staging")

        from_name.assert_called_once_with(
            "simulation-api-uk-versions", environment_name="staging"
        )

    def test_lru_cache_returns_same_result(self):
        """Repeated calls with same args hit cache, not Modal Dict."""
        mock_dict = MagicMock()
        mock_dict.__getitem__ = MagicMock(return_value="cached-app")

        with patch("modal.Dict.from_name", return_value=mock_dict) as from_name:
            result1 = _resolve_app_name("us", "1.0.0", "main")
            result2 = _resolve_app_name("us", "1.0.0", "main")

        assert result1 == result2
        # Dict.from_name called only once due to cache
        from_name.assert_called_once()

    def test_raises_key_error_for_unknown_version(self):
        """Unknown version raises KeyError (not caught here)."""
        mock_dict = MagicMock()
        mock_dict.__getitem__ = MagicMock(side_effect=KeyError("2.0.0"))

        with patch("modal.Dict.from_name", return_value=mock_dict):
            with pytest.raises(KeyError):
                _resolve_app_name("us", "2.0.0", "main")


class TestResolveModalFunction:
    """Tests for resolve_modal_function (public API with fallback)."""

    @patch("policyengine_api.version_resolver.modal.Function.from_name")
    def test_fallback_on_key_error(self, mock_from_name):
        """KeyError from Dict lookup falls back to legacy app."""
        mock_dict = MagicMock()
        mock_dict.__getitem__ = MagicMock(side_effect=KeyError("latest"))

        with patch("modal.Dict.from_name", return_value=mock_dict):
            with patch(
                "policyengine_api.config.settings"
            ) as mock_settings:
                mock_settings.modal_environment = "main"
                resolve_modal_function("simulate_household_us", "us")

        # Should fall back to "policyengine" (legacy)
        mock_from_name.assert_called_with(
            "policyengine",
            "simulate_household_us",
            environment_name="main",
        )

    @patch("policyengine_api.version_resolver.modal.Function.from_name")
    def test_successful_resolution(self, mock_from_name):
        """Successful resolution calls from_name with versioned app."""
        mock_dict = MagicMock()
        mock_dict.__getitem__ = MagicMock(
            side_effect=lambda key: {
                "latest": "1.592.4",
                "1.592.4": "policyengine-v2-us1-592-4-uk2-75-1",
            }[key]
        )

        with patch("modal.Dict.from_name", return_value=mock_dict):
            with patch(
                "policyengine_api.config.settings"
            ) as mock_settings:
                mock_settings.modal_environment = "main"
                resolve_modal_function("economy_comparison_uk", "uk")

        mock_from_name.assert_called_with(
            "policyengine-v2-us1-592-4-uk2-75-1",
            "economy_comparison_uk",
            environment_name="main",
        )
