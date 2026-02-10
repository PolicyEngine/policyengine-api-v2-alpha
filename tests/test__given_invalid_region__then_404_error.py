"""Tests for region resolution error cases.

When an invalid region code is provided or required parameters are missing,
appropriate HTTP errors should be raised.
"""

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from policyengine_api.api.analysis import (
    EconomicImpactRequest,
    _resolve_dataset_and_region,
)
from test_fixtures.fixtures_regions import (
    create_dataset,
    create_region,
    create_tax_benefit_model,
)


class TestInvalidRegionCode:
    """Tests for invalid region code handling."""

    def test_given_nonexistent_region_code_then_raises_404(self, session: Session):
        """Given a region code that doesn't exist, then raises 404."""
        # Given
        model = create_tax_benefit_model(session, name="policyengine-uk")
        dataset = create_dataset(session, model, name="uk_enhanced_frs")
        # Note: No region is created for this code
        request = EconomicImpactRequest(
            tax_benefit_model_name="policyengine_uk",
            region="nonexistent/region",
        )

        # When/Then
        with pytest.raises(HTTPException) as exc_info:
            _resolve_dataset_and_region(request, session)

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

    def test_given_region_for_wrong_model_then_raises_404(self, session: Session):
        """Given a region code for wrong model, then raises 404."""
        # Given
        uk_model = create_tax_benefit_model(session, name="policyengine-uk")
        uk_dataset = create_dataset(session, uk_model, name="uk_enhanced_frs")
        create_region(
            session,
            model=uk_model,
            dataset=uk_dataset,
            code="uk",
            label="United Kingdom",
            region_type="national",
        )
        # Request uses US model but UK region code
        request = EconomicImpactRequest(
            tax_benefit_model_name="policyengine_us",
            region="uk",
        )

        # When/Then
        with pytest.raises(HTTPException) as exc_info:
            _resolve_dataset_and_region(request, session)

        assert exc_info.value.status_code == 404


class TestMissingRequiredParams:
    """Tests for missing required parameters."""

    def test_given_neither_dataset_nor_region_then_raises_400(self, session: Session):
        """Given neither dataset_id nor region, then raises 400."""
        # Given
        request = EconomicImpactRequest(
            tax_benefit_model_name="policyengine_uk",
            # Neither dataset_id nor region provided
        )

        # When/Then
        with pytest.raises(HTTPException) as exc_info:
            _resolve_dataset_and_region(request, session)

        assert exc_info.value.status_code == 400
        assert "either dataset_id or region" in exc_info.value.detail.lower()


class TestNonexistentDataset:
    """Tests for nonexistent dataset handling."""

    def test_given_nonexistent_dataset_id_then_raises_404(self, session: Session):
        """Given a dataset_id that doesn't exist, then raises 404."""
        # Given
        from uuid import uuid4

        nonexistent_id = uuid4()
        request = EconomicImpactRequest(
            tax_benefit_model_name="policyengine_uk",
            dataset_id=nonexistent_id,
        )

        # When/Then
        with pytest.raises(HTTPException) as exc_info:
            _resolve_dataset_and_region(request, session)

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()
