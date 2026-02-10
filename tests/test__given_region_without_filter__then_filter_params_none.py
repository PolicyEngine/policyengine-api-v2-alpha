"""Tests for region resolution without filter parameters.

When a region does not require filtering (e.g., national UK or US),
the filter_field and filter_value should be None.
"""

import pytest
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


class TestResolveDatasetAndRegionWithoutFilter:
    """Tests for _resolve_dataset_and_region when region does not require filtering."""

    def test_given_national_uk_region_then_filter_params_none(self, session: Session):
        """Given UK national region, then filter_field and filter_value are None."""
        # Given
        model = create_tax_benefit_model(session, name="policyengine-uk")
        dataset = create_dataset(session, model, name="uk_enhanced_frs")
        region = create_region(
            session,
            model=model,
            dataset=dataset,
            code="uk",
            label="United Kingdom",
            region_type="national",
            requires_filter=False,
        )
        request = EconomicImpactRequest(
            tax_benefit_model_name="policyengine_uk",
            region="uk",
        )

        # When
        resolved_dataset, resolved_region = _resolve_dataset_and_region(
            request, session
        )

        # Then
        assert resolved_region is not None
        assert resolved_region.requires_filter is False
        assert resolved_region.filter_field is None
        assert resolved_region.filter_value is None

    def test_given_national_us_region_then_filter_params_none(self, session: Session):
        """Given US national region, then filter_field and filter_value are None."""
        # Given
        model = create_tax_benefit_model(session, name="policyengine-us")
        dataset = create_dataset(session, model, name="us_cps")
        region = create_region(
            session,
            model=model,
            dataset=dataset,
            code="us",
            label="United States",
            region_type="national",
            requires_filter=False,
        )
        request = EconomicImpactRequest(
            tax_benefit_model_name="policyengine_us",
            region="us",
        )

        # When
        resolved_dataset, resolved_region = _resolve_dataset_and_region(
            request, session
        )

        # Then
        assert resolved_region is not None
        assert resolved_region.requires_filter is False
        assert resolved_region.filter_field is None
        assert resolved_region.filter_value is None

    def test_given_national_region_then_dataset_still_resolved(self, session: Session):
        """Given national region without filter, then dataset is still correctly resolved."""
        # Given
        model = create_tax_benefit_model(session, name="policyengine-uk")
        dataset = create_dataset(session, model, name="uk_enhanced_frs")
        region = create_region(
            session,
            model=model,
            dataset=dataset,
            code="uk",
            label="United Kingdom",
            region_type="national",
            requires_filter=False,
        )
        request = EconomicImpactRequest(
            tax_benefit_model_name="policyengine_uk",
            region="uk",
        )

        # When
        resolved_dataset, resolved_region = _resolve_dataset_and_region(
            request, session
        )

        # Then
        assert resolved_dataset.id == dataset.id
        assert resolved_dataset.name == "uk_enhanced_frs"
