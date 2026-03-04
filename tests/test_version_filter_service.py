"""Tests for the tax benefit model version resolution service."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException

from policyengine_api.models import TaxBenefitModel, TaxBenefitModelVersion
from policyengine_api.services.tax_benefit_models import (
    get_latest_model_version,
    get_model_version_by_id,
    resolve_model_version_id,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def us_model(session):
    """Create a policyengine-us model."""
    model = TaxBenefitModel(name="policyengine-us", description="US model")
    session.add(model)
    session.commit()
    session.refresh(model)
    return model


@pytest.fixture
def us_versions(session, us_model):
    """Create two versions for the US model, v1 older than v2."""
    v1 = TaxBenefitModelVersion(
        model_id=us_model.id,
        version="1.0.0",
        description="First version",
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    v2 = TaxBenefitModelVersion(
        model_id=us_model.id,
        version="2.0.0",
        description="Second version",
        created_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
    )
    session.add(v1)
    session.add(v2)
    session.commit()
    session.refresh(v1)
    session.refresh(v2)
    return v1, v2


# ---------------------------------------------------------------------------
# get_latest_model_version
# ---------------------------------------------------------------------------


class TestGetLatestModelVersion:
    def test_returns_latest_version(self, session, us_model, us_versions):
        """Given multiple versions, returns the one with the newest created_at."""
        v1, v2 = us_versions
        result = get_latest_model_version("policyengine-us", session)
        assert result.id == v2.id
        assert result.version == "2.0.0"

    def test_normalizes_underscores_to_hyphens(self, session, us_model, us_versions):
        """Underscore names like 'policyengine_us' are normalized."""
        v1, v2 = us_versions
        result = get_latest_model_version("policyengine_us", session)
        assert result.id == v2.id

    def test_nonexistent_model_raises_404(self, session):
        """A model name that doesn't exist raises HTTPException 404."""
        with pytest.raises(HTTPException) as exc_info:
            get_latest_model_version("nonexistent-model", session)
        assert exc_info.value.status_code == 404

    def test_model_with_no_versions_raises_404(self, session, us_model):
        """A model that exists but has no versions raises HTTPException 404."""
        with pytest.raises(HTTPException) as exc_info:
            get_latest_model_version("policyengine-us", session)
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# get_model_version_by_id
# ---------------------------------------------------------------------------


class TestGetModelVersionById:
    def test_returns_version(self, session, us_versions):
        """Given a valid version UUID, returns that version."""
        v1, v2 = us_versions
        result = get_model_version_by_id(v1.id, session)
        assert result.id == v1.id
        assert result.version == "1.0.0"

    def test_nonexistent_id_raises_404(self, session):
        """A UUID that doesn't match any version raises HTTPException 404."""
        with pytest.raises(HTTPException) as exc_info:
            get_model_version_by_id(uuid4(), session)
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# resolve_model_version_id
# ---------------------------------------------------------------------------


class TestResolveModelVersionId:
    def test_version_id_takes_precedence(self, session, us_versions):
        """When both model name and version ID are given, version ID wins."""
        v1, v2 = us_versions
        result = resolve_model_version_id("policyengine-us", v1.id, session)
        assert result == v1.id

    def test_model_name_resolves_to_latest(self, session, us_model, us_versions):
        """When only model name is given, resolves to the latest version."""
        v1, v2 = us_versions
        result = resolve_model_version_id("policyengine-us", None, session)
        assert result == v2.id

    def test_neither_returns_none(self, session):
        """When neither model name nor version ID is given, returns None."""
        result = resolve_model_version_id(None, None, session)
        assert result is None

    def test_invalid_version_id_raises_404(self, session):
        """An explicit version ID that doesn't exist raises 404."""
        with pytest.raises(HTTPException) as exc_info:
            resolve_model_version_id(None, uuid4(), session)
        assert exc_info.value.status_code == 404
