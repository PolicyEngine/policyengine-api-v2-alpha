"""Tests for _run_simulation_in_session status handling (Critical #3 fix)."""

from uuid import uuid4

import pytest

from policyengine_api.api.household_analysis import _run_simulation_in_session
from policyengine_api.models import (
    Household,
    Simulation,
    SimulationStatus,
    SimulationType,
    TaxBenefitModel,
    TaxBenefitModelVersion,
)


def _setup_household_simulation(session, status=SimulationStatus.PENDING):
    """Create a household + simulation for testing."""
    model = TaxBenefitModel(name="policyengine-us", description="US")
    session.add(model)
    session.commit()
    session.refresh(model)

    version = TaxBenefitModelVersion(model_id=model.id, version="1.0", description="V1")
    session.add(version)
    session.commit()
    session.refresh(version)

    household = Household(
        country_id="us",
        household_data={"people": {"you": {"age": {"2024": 30}}}},
        year=2024,
    )
    session.add(household)
    session.commit()
    session.refresh(household)

    sim = Simulation(
        tax_benefit_model_version_id=version.id,
        status=status,
        simulation_type=SimulationType.HOUSEHOLD,
        household_id=household.id,
    )
    session.add(sim)
    session.commit()
    session.refresh(sim)
    return sim


class TestRunSimulationInSession:
    def test_missing_simulation_raises_valueerror(self, session):
        with pytest.raises(ValueError, match="not found"):
            _run_simulation_in_session(uuid4(), session)

    def test_completed_simulation_skips_silently(self, session):
        sim = _setup_household_simulation(session, SimulationStatus.COMPLETED)
        # Should not raise
        _run_simulation_in_session(sim.id, session)
        # Status should still be COMPLETED
        session.refresh(sim)
        assert sim.status == SimulationStatus.COMPLETED

    def test_running_simulation_raises_valueerror(self, session):
        sim = _setup_household_simulation(session, SimulationStatus.RUNNING)
        with pytest.raises(ValueError, match="unexpected status"):
            _run_simulation_in_session(sim.id, session)

    def test_failed_simulation_raises_valueerror(self, session):
        sim = _setup_household_simulation(session, SimulationStatus.FAILED)
        with pytest.raises(ValueError, match="unexpected status"):
            _run_simulation_in_session(sim.id, session)
