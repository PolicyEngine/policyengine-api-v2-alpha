"""Tests for the tax benefit model version resolution service."""

from uuid import uuid4

import pytest
from fastapi import HTTPException

from policyengine_api.services.tax_benefit_models import (
    get_latest_model_version,
    get_model_version_by_id,
    resolve_model_version_id,
)
from test_fixtures.fixtures_version_filter import (
    MODEL_NAMES,
    create_model,
    create_version,
    us_model,  # noqa: F401
    us_two_versions,  # noqa: F401
)

# ---------------------------------------------------------------------------
# get_latest_model_version
# ---------------------------------------------------------------------------


class TestGetLatestModelVersion:
    def test_given_multiple_versions_then_returns_newest(
        self,
        session,
        us_model,  # noqa: F811
        us_two_versions,  # noqa: F811
    ):
        """Returns the version with the most recent created_at."""
        _v1, v2 = us_two_versions
        result = get_latest_model_version(MODEL_NAMES["US"], session)
        assert result.id == v2.id
        assert result.version == "2.0"

    def test_given_underscore_name_then_normalizes_to_hyphens(
        self,
        session,
        us_model,  # noqa: F811
        us_two_versions,  # noqa: F811
    ):
        """'policyengine_us' is normalised to 'policyengine-us'."""
        _v1, v2 = us_two_versions
        result = get_latest_model_version("policyengine_us", session)
        assert result.id == v2.id

    def test_given_nonexistent_model_then_raises_404(self, session):
        """Unknown model name raises HTTPException 404."""
        with pytest.raises(HTTPException) as exc_info:
            get_latest_model_version("nonexistent-model", session)
        assert exc_info.value.status_code == 404

    def test_given_model_without_versions_then_raises_404(
        self,
        session,
        us_model,  # noqa: F811
    ):
        """Model that exists but has zero versions raises 404."""
        with pytest.raises(HTTPException) as exc_info:
            get_latest_model_version(MODEL_NAMES["US"], session)
        assert exc_info.value.status_code == 404

    def test_given_single_version_then_returns_it(self, session):
        """With only one version, that version is returned."""
        model = create_model(session)
        only = create_version(session, model, "0.1")
        result = get_latest_model_version(MODEL_NAMES["US"], session)
        assert result.id == only.id


# ---------------------------------------------------------------------------
# get_model_version_by_id
# ---------------------------------------------------------------------------


class TestGetModelVersionById:
    def test_given_valid_id_then_returns_version(
        self,
        session,
        us_two_versions,  # noqa: F811
    ):
        """Returns the matching version."""
        v1, _v2 = us_two_versions
        result = get_model_version_by_id(v1.id, session)
        assert result.id == v1.id
        assert result.version == "1.0"

    def test_given_nonexistent_id_then_raises_404(self, session):
        """Unknown UUID raises HTTPException 404."""
        with pytest.raises(HTTPException) as exc_info:
            get_model_version_by_id(uuid4(), session)
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# resolve_model_version_id
# ---------------------------------------------------------------------------


class TestResolveModelVersionId:
    def test_given_version_id_then_takes_precedence_over_model_name(
        self,
        session,
        us_two_versions,  # noqa: F811
    ):
        """Explicit version_id wins over model_name."""
        v1, _v2 = us_two_versions
        result = resolve_model_version_id(MODEL_NAMES["US"], v1.id, session)
        assert result == v1.id

    def test_given_only_model_name_then_resolves_to_latest(
        self,
        session,
        us_model,  # noqa: F811
        us_two_versions,  # noqa: F811
    ):
        """Model name alone returns the latest version's ID."""
        _v1, v2 = us_two_versions
        result = resolve_model_version_id(MODEL_NAMES["US"], None, session)
        assert result == v2.id

    def test_given_neither_then_returns_none(self, session):
        """No model name and no version ID → None (no filtering)."""
        result = resolve_model_version_id(None, None, session)
        assert result is None

    def test_given_invalid_version_id_then_raises_404(self, session):
        """Non-existent explicit version_id raises 404."""
        with pytest.raises(HTTPException) as exc_info:
            resolve_model_version_id(None, uuid4(), session)
        assert exc_info.value.status_code == 404

    def test_given_invalid_model_name_then_raises_404(self, session):
        """Non-existent model name raises 404."""
        with pytest.raises(HTTPException) as exc_info:
            resolve_model_version_id("does-not-exist", None, session)
        assert exc_info.value.status_code == 404
