"""Tests for simulation reuse with filter parameters.

When a simulation with the same parameters already exists,
it should be reused instead of creating a new one.
"""

import pytest
from sqlmodel import Session

from policyengine_api.api.analysis import _get_or_create_simulation
from policyengine_api.models import SimulationStatus, SimulationType
from test_fixtures.fixtures_regions import (
    create_dataset,
    create_simulation,
    create_tax_benefit_model,
    create_tax_benefit_model_version,
)


class TestSimulationReuse:
    """Tests for simulation reuse behavior."""

    def test_given_existing_simulation_with_filter_then_reuses(self, session: Session):
        """Given an existing simulation with filter params, then it is reused."""
        # Given
        model = create_tax_benefit_model(session, name="policyengine-uk")
        model_version = create_tax_benefit_model_version(session, model)
        dataset = create_dataset(session, model, name="uk_enhanced_frs")

        # Create initial simulation with filter params
        first_sim = _get_or_create_simulation(
            simulation_type=SimulationType.ECONOMY,
            dataset_id=dataset.id,
            model_version_id=model_version.id,
            policy_id=None,
            dynamic_id=None,
            session=session,
            filter_field="country",
            filter_value="ENGLAND",
        )

        # When - request same simulation again
        second_sim = _get_or_create_simulation(
            simulation_type=SimulationType.ECONOMY,
            dataset_id=dataset.id,
            model_version_id=model_version.id,
            policy_id=None,
            dynamic_id=None,
            session=session,
            filter_field="country",
            filter_value="ENGLAND",
        )

        # Then
        assert first_sim.id == second_sim.id

    def test_given_different_filter_then_creates_new_simulation(self, session: Session):
        """Given different filter params, then a new simulation is created."""
        # Given
        model = create_tax_benefit_model(session, name="policyengine-uk")
        model_version = create_tax_benefit_model_version(session, model)
        dataset = create_dataset(session, model, name="uk_enhanced_frs")

        # Create simulation for England
        england_sim = _get_or_create_simulation(
            simulation_type=SimulationType.ECONOMY,
            dataset_id=dataset.id,
            model_version_id=model_version.id,
            policy_id=None,
            dynamic_id=None,
            session=session,
            filter_field="country",
            filter_value="ENGLAND",
        )

        # When - request simulation for Scotland
        scotland_sim = _get_or_create_simulation(
            simulation_type=SimulationType.ECONOMY,
            dataset_id=dataset.id,
            model_version_id=model_version.id,
            policy_id=None,
            dynamic_id=None,
            session=session,
            filter_field="country",
            filter_value="SCOTLAND",
        )

        # Then
        assert england_sim.id != scotland_sim.id
        assert england_sim.filter_value == "ENGLAND"
        assert scotland_sim.filter_value == "SCOTLAND"

    def test_given_no_filter_vs_filter_then_creates_separate_simulations(
        self, session: Session
    ):
        """Given national vs filtered, then separate simulations are created."""
        # Given
        model = create_tax_benefit_model(session, name="policyengine-uk")
        model_version = create_tax_benefit_model_version(session, model)
        dataset = create_dataset(session, model, name="uk_enhanced_frs")

        # Create national (no filter) simulation
        national_sim = _get_or_create_simulation(
            simulation_type=SimulationType.ECONOMY,
            dataset_id=dataset.id,
            model_version_id=model_version.id,
            policy_id=None,
            dynamic_id=None,
            session=session,
            filter_field=None,
            filter_value=None,
        )

        # When - request filtered simulation
        filtered_sim = _get_or_create_simulation(
            simulation_type=SimulationType.ECONOMY,
            dataset_id=dataset.id,
            model_version_id=model_version.id,
            policy_id=None,
            dynamic_id=None,
            session=session,
            filter_field="country",
            filter_value="ENGLAND",
        )

        # Then
        assert national_sim.id != filtered_sim.id
        assert national_sim.filter_field is None
        assert filtered_sim.filter_field == "country"

    def test_given_new_simulation_then_status_is_pending(self, session: Session):
        """Given a new simulation request, then status is PENDING."""
        # Given
        model = create_tax_benefit_model(session, name="policyengine-uk")
        model_version = create_tax_benefit_model_version(session, model)
        dataset = create_dataset(session, model, name="uk_enhanced_frs")

        # When
        simulation = _get_or_create_simulation(
            simulation_type=SimulationType.ECONOMY,
            dataset_id=dataset.id,
            model_version_id=model_version.id,
            policy_id=None,
            dynamic_id=None,
            session=session,
            filter_field="country",
            filter_value="ENGLAND",
        )

        # Then
        assert simulation.status == SimulationStatus.PENDING
