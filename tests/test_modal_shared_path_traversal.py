"""Regression test for path traversal in ``download_dataset`` (#274)."""

import pytest

from policyengine_api.modal.shared import download_dataset


def test_download_dataset_rejects_path_traversal():
    """Relative parents ('../../...') must not escape the cache root."""
    with pytest.raises(ValueError) as exc:
        download_dataset(
            filepath="../../etc/passwd",
            supabase_url="http://example.test",
            supabase_key="anon",
            storage_bucket="datasets",
        )
    assert "Path traversal" in str(exc.value)


def test_download_dataset_rejects_absolute_path():
    with pytest.raises(ValueError):
        download_dataset(
            filepath="/etc/passwd",
            supabase_url="http://example.test",
            supabase_key="anon",
            storage_bucket="datasets",
        )
