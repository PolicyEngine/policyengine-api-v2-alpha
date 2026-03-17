"""Tests for scripts/seed_utils.py bulk_insert serialization."""

import json
import sys
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

# Mock the settings module before importing seed_utils,
# since seed_utils has module-level imports that require env vars.
mock_settings = MagicMock()
mock_settings.logfire_token = None
mock_settings.database_url = "sqlite://"
sys.modules["policyengine_api.config.settings"] = MagicMock(settings=mock_settings)
sys.modules["policyengine_api.config"] = MagicMock(settings=mock_settings)

from scripts.seed_utils import bulk_insert  # noqa: E402


@pytest.fixture
def mock_session():
    """Create a mock SQLModel session with a captured copy_from call."""
    session = MagicMock()
    cursor = MagicMock()
    session.connection().connection.dbapi_connection.cursor.return_value = cursor
    return session, cursor


def _capture_copy_buffer(mock_cursor) -> str:
    """Extract the StringIO content passed to copy_from."""
    call_args = mock_cursor.copy_from.call_args
    buffer = call_args[0][0]
    buffer.seek(0)
    return buffer.read()


class TestBulkInsertSerialization:
    def test_list_serialized_as_json(self, mock_session):
        """Lists should be serialized with json.dumps (double quotes), not str() (single quotes)."""
        session, cursor = mock_session
        rows = [{"adds": ["child_benefit", "housing_benefit"]}]

        bulk_insert(session, "variables", ["adds"], rows)

        content = _capture_copy_buffer(cursor)
        assert '["child_benefit", "housing_benefit"]' in content
        assert "['child_benefit'" not in content

    def test_dict_serialized_as_json(self, mock_session):
        """Dicts should be serialized with json.dumps."""
        session, cursor = mock_session
        rows = [{"metadata": {"key": "value", "nested": True}}]

        bulk_insert(session, "test_table", ["metadata"], rows)

        content = _capture_copy_buffer(cursor)
        parsed = json.loads(content.strip())
        assert parsed == {"key": "value", "nested": True}

    def test_empty_list_serialized_as_json(self, mock_session):
        """Empty lists should produce valid JSON."""
        session, cursor = mock_session
        rows = [{"adds": []}]

        bulk_insert(session, "variables", ["adds"], rows)

        content = _capture_copy_buffer(cursor)
        assert "[]" in content

    def test_none_serialized_as_null(self, mock_session):
        """None values should produce \\N for Postgres COPY null."""
        session, cursor = mock_session
        rows = [{"adds": None}]

        bulk_insert(session, "variables", ["adds"], rows)

        content = _capture_copy_buffer(cursor)
        assert "\\N" in content

    def test_string_with_special_chars_escaped(self, mock_session):
        """Strings with tabs and newlines should be escaped."""
        session, cursor = mock_session
        rows = [{"description": "line1\tline2\nline3"}]

        bulk_insert(session, "variables", ["description"], rows)

        content = _capture_copy_buffer(cursor)
        assert "\\t" in content
        assert "\\n" in content

    def test_multiple_columns_with_mixed_types(self, mock_session):
        """Verify correct serialization across multiple column types in one row."""
        session, cursor = mock_session
        row_id = uuid4()
        rows = [
            {
                "id": row_id,
                "name": "income_tax",
                "adds": ["gross_income"],
                "subtracts": [],
                "description": None,
            }
        ]
        columns = ["id", "name", "adds", "subtracts", "description"]

        bulk_insert(session, "variables", columns, rows)

        content = _capture_copy_buffer(cursor)
        parts = content.strip().split("\t")
        assert parts[0] == str(row_id)
        assert parts[1] == "income_tax"
        assert parts[2] == '["gross_income"]'
        assert parts[3] == "[]"
        assert parts[4] == "\\N"

    def test_empty_rows_skips_copy(self, mock_session):
        """Empty row list should return without calling copy_from."""
        session, cursor = mock_session

        bulk_insert(session, "variables", ["adds"], [])

        cursor.copy_from.assert_not_called()
