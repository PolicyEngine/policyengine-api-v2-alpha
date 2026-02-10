"""Tests for region resolution with filter parameters.

When a region requires filtering (e.g., England from UK dataset,
California from US dataset), the filter_field and filter_value
should be extracted and passed through to simulations.
"""

import pytest
from sqlmodel import Session

from policyengine_api.api.analysis import (
    EconomicImpactRequest,
    _get_or_create_simulation,
    _resolve_dataset_and_region,
)
from test_fixtures.fixtures_regions import (
    create_dataset,
    create_region,
    create_tax_benefit_model,
    create_tax_benefit_model_version,
)


class TestResolveDatasetAndRegionWithFilter:
    """Tests for _resolve_dataset_and_region when region requires filtering."""

    def test_given_region_requires_filter_then_returns_filter_field(
        self, session: Session
    ):
        """Given a region that requires filtering, then filter_field is populated."""
        # Given
        model = create_tax_benefit_model(session, name="policyengine-uk")
        dataset = create_dataset(session, model, name="uk_enhanced_frs")
        region = create_region(
            session,
            model=model,
            dataset=dataset,
            code="country/england",
            label="England",
            region_type="country",
            requires_filter=True,
            filter_field="country",
            filter_value="ENGLAND",
        )
        request = EconomicImpactRequest(
            tax_benefit_model_name="policyengine_uk",
            region="country/england",
        )

        # When
        resolved_dataset, resolved_region = _resolve_dataset_and_region(
            request, session
        )

        # Then
        assert resolved_region is not None
        assert resolved_region.filter_field == "country"
        assert resolved_region.filter_value == "ENGLAND"
        assert resolved_region.requires_filter is True

    def test_given_us_state_region_then_returns_state_filter(self, session: Session):
        """Given a US state region, then returns state code filter."""
        # Given
        model = create_tax_benefit_model(session, name="policyengine-us")
        dataset = create_dataset(session, model, name="us_cps")
        region = create_region(
            session,
            model=model,
            dataset=dataset,
            code="state/ca",
            label="California",
            region_type="state",
            requires_filter=True,
            filter_field="state_code",
            filter_value="CA",
        )
        request = EconomicImpactRequest(
            tax_benefit_model_name="policyengine_us",
            region="state/ca",
        )

        # When
        resolved_dataset, resolved_region = _resolve_dataset_and_region(
            request, session
        )

        # Then
        assert resolved_region is not None
        assert resolved_region.filter_field == "state_code"
        assert resolved_region.filter_value == "CA"

    def test_given_region_with_filter_then_dataset_is_resolved(self, session: Session):
        """Given a region code, then the associated dataset is returned."""
        # Given
        model = create_tax_benefit_model(session, name="policyengine-uk")
        dataset = create_dataset(session, model, name="uk_enhanced_frs")
        region = create_region(
            session,
            model=model,
            dataset=dataset,
            code="country/england",
            label="England",
            region_type="country",
            requires_filter=True,
            filter_field="country",
            filter_value="ENGLAND",
        )
        request = EconomicImpactRequest(
            tax_benefit_model_name="policyengine_uk",
            region="country/england",
        )

        # When
        resolved_dataset, resolved_region = _resolve_dataset_and_region(
            request, session
        )

        # Then
        assert resolved_dataset.id == dataset.id
        assert resolved_dataset.name == "uk_enhanced_frs"


class TestSimulationCreationWithFilter:
    """Tests for creating simulations with filter parameters."""

    def test_given_filter_params_then_simulation_has_filter_fields(
        self, session: Session
    ):
        """Given filter parameters, then created simulation has filter fields populated."""
        # Given
        model = create_tax_benefit_model(session, name="policyengine-uk")
        model_version = create_tax_benefit_model_version(session, model)
        dataset = create_dataset(session, model, name="uk_enhanced_frs")

        # When
        simulation = _get_or_create_simulation(
            dataset_id=dataset.id,
            model_version_id=model_version.id,
            policy_id=None,
            dynamic_id=None,
            session=session,
            filter_field="country",
            filter_value="ENGLAND",
        )

        # Then
        assert simulation.filter_field == "country"
        assert simulation.filter_value == "ENGLAND"

    def test_given_no_filter_params_then_simulation_has_null_filter_fields(
        self, session: Session
    ):
        """Given no filter parameters, then created simulation has null filter fields."""
        # Given
        model = create_tax_benefit_model(session, name="policyengine-uk")
        model_version = create_tax_benefit_model_version(session, model)
        dataset = create_dataset(session, model, name="uk_enhanced_frs")

        # When
        simulation = _get_or_create_simulation(
            dataset_id=dataset.id,
            model_version_id=model_version.id,
            policy_id=None,
            dynamic_id=None,
            session=session,
        )

        # Then
        assert simulation.filter_field is None
        assert simulation.filter_value is None
