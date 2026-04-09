"""Tests for update_version_registry script."""

from unittest.mock import MagicMock, patch

from scripts.update_version_registry import update_version_dict


class TestUpdateVersionDict:
    """Tests for update_version_dict function."""

    def test_creates_new_entry(self):
        """New version creates entry and sets latest."""
        mock_dict = MagicMock()
        mock_dict.__getitem__ = MagicMock(side_effect=KeyError("1.592.4"))
        mock_dict.get = MagicMock(return_value=None)

        with patch("modal.Dict.from_name", return_value=mock_dict):
            update_version_dict(
                "api-v2-us-versions",
                "staging",
                "1.592.4",
                "policyengine-v2-us1-592-4-uk2-75-1",
            )

        mock_dict.__setitem__.assert_any_call(
            "1.592.4", "policyengine-v2-us1-592-4-uk2-75-1"
        )
        mock_dict.__setitem__.assert_any_call("latest", "1.592.4")

    def test_updates_existing_entry(self):
        """Existing version updates app name."""
        mock_dict = MagicMock()
        mock_dict.__getitem__ = MagicMock(return_value="old-app-name")
        mock_dict.get = MagicMock(return_value="1.592.4")

        with patch("modal.Dict.from_name", return_value=mock_dict):
            update_version_dict(
                "api-v2-us-versions",
                "main",
                "1.592.4",
                "new-app-name",
            )

        mock_dict.__setitem__.assert_any_call("1.592.4", "new-app-name")

    def test_sets_latest_to_new_version(self):
        """Latest key is updated to the new version string."""
        mock_dict = MagicMock()
        mock_dict.__getitem__ = MagicMock(side_effect=KeyError("2.0.0"))
        mock_dict.get = MagicMock(return_value="1.0.0")

        with patch("modal.Dict.from_name", return_value=mock_dict):
            update_version_dict(
                "api-v2-uk-versions",
                "staging",
                "2.0.0",
                "app-v2",
            )

        mock_dict.__setitem__.assert_any_call("latest", "2.0.0")

    def test_passes_environment_to_modal(self):
        """Environment flag is forwarded to modal.Dict.from_name."""
        mock_dict = MagicMock()
        mock_dict.__getitem__ = MagicMock(side_effect=KeyError)
        mock_dict.get = MagicMock(return_value=None)

        with patch("modal.Dict.from_name", return_value=mock_dict) as from_name:
            update_version_dict(
                "api-v2-us-versions",
                "staging",
                "1.0.0",
                "app",
            )

        from_name.assert_called_once_with(
            "api-v2-us-versions",
            environment_name="staging",
            create_if_missing=True,
        )

    def test_create_if_missing_flag(self):
        """Dict is created if it doesn't exist (create_if_missing=True)."""
        mock_dict = MagicMock()
        mock_dict.__getitem__ = MagicMock(side_effect=KeyError)
        mock_dict.get = MagicMock(return_value=None)

        with patch("modal.Dict.from_name", return_value=mock_dict) as from_name:
            update_version_dict(
                "api-v2-uk-versions",
                "main",
                "2.75.1",
                "app-uk",
            )

        _, kwargs = from_name.call_args
        assert kwargs["create_if_missing"] is True
