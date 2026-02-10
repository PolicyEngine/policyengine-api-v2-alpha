"""Tests for dataset resolution when dataset_id is provided directly.

When a dataset_id is provided instead of a region code,
the resolved region should be None.
"""

import pytest
from sqlmodel import Session

from policyengine_api.api.analysis import (
    EconomicImpactRequest,
    _resolve_dataset_and_region,
)
from test_fixtures.fixtures_regions import (
    create_dataset,
    create_tax_benefit_model,
)


class TestResolveDatasetWithDatasetId:
    """Tests for _resolve_dataset_and_region when dataset_id is provided."""

    def test_given_dataset_id_then_region_is_none(self, session: Session):
        """Given a dataset_id, then region is None in the response."""
        # Given
        model = create_tax_benefit_model(session, name="policyengine-uk")
        dataset = create_dataset(session, model, name="uk_enhanced_frs")
        request = EconomicImpactRequest(
            tax_benefit_model_name="policyengine_uk",
            dataset_id=dataset.id,
        )

        # When
        resolved_dataset, resolved_region = _resolve_dataset_and_region(
            request, session
        )

        # Then
        assert resolved_region is None

    def test_given_dataset_id_then_dataset_is_returned(self, session: Session):
        """Given a dataset_id, then the correct dataset is returned."""
        # Given
        model = create_tax_benefit_model(session, name="policyengine-uk")
        dataset = create_dataset(session, model, name="uk_enhanced_frs")
        request = EconomicImpactRequest(
            tax_benefit_model_name="policyengine_uk",
            dataset_id=dataset.id,
        )

        # When
        resolved_dataset, resolved_region = _resolve_dataset_and_region(
            request, session
        )

        # Then
        assert resolved_dataset.id == dataset.id
        assert resolved_dataset.name == "uk_enhanced_frs"

    def test_given_dataset_id_and_region_then_region_takes_precedence(
        self, session: Session
    ):
        """Given both dataset_id and region, then region takes precedence."""
        # Given
        model = create_tax_benefit_model(session, name="policyengine-uk")
        dataset1 = create_dataset(session, model, name="dataset_from_id")
        dataset2 = create_dataset(session, model, name="dataset_from_region")
        from test_fixtures.fixtures_regions import create_region

        region = create_region(
            session,
            model=model,
            dataset=dataset2,
            code="uk",
            label="United Kingdom",
            region_type="national",
            requires_filter=False,
        )
        request = EconomicImpactRequest(
            tax_benefit_model_name="policyengine_uk",
            dataset_id=dataset1.id,
            region="uk",
        )

        # When
        resolved_dataset, resolved_region = _resolve_dataset_and_region(
            request, session
        )

        # Then
        # Region code takes precedence, so we get dataset2
        assert resolved_dataset.id == dataset2.id
        assert resolved_region is not None
        assert resolved_region.code == "uk"
