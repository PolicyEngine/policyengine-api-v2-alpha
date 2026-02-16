"""Tests for deterministic simulation ID generation.

The simulation ID is generated deterministically from the simulation
parameters (dataset, model version, policy, dynamic, filter params).
This ensures that re-running the same simulation reuses existing results.
"""

from uuid import uuid4

import pytest

from policyengine_api.api.analysis import _get_deterministic_simulation_id
from policyengine_api.models import SimulationType


class TestDeterministicSimulationId:
    """Tests for _get_deterministic_simulation_id function."""

    def test_given_same_params_then_same_id_returned(self):
        """Given identical parameters, then the same ID is returned."""
        # Given
        dataset_id = uuid4()
        model_version_id = uuid4()
        policy_id = uuid4()
        dynamic_id = uuid4()
        filter_field = "country"
        filter_value = "ENGLAND"

        # When
        id1 = _get_deterministic_simulation_id(
            SimulationType.ECONOMY,
            model_version_id,
            policy_id,
            dynamic_id,
            dataset_id=dataset_id,
            filter_field=filter_field,
            filter_value=filter_value,
        )
        id2 = _get_deterministic_simulation_id(
            SimulationType.ECONOMY,
            model_version_id,
            policy_id,
            dynamic_id,
            dataset_id=dataset_id,
            filter_field=filter_field,
            filter_value=filter_value,
        )

        # Then
        assert id1 == id2

    def test_given_different_filter_field_then_different_id(self):
        """Given different filter_field, then a different ID is returned."""
        # Given
        dataset_id = uuid4()
        model_version_id = uuid4()
        policy_id = None
        dynamic_id = None

        # When
        id1 = _get_deterministic_simulation_id(
            SimulationType.ECONOMY,
            model_version_id,
            policy_id,
            dynamic_id,
            dataset_id=dataset_id,
            filter_field="country",
            filter_value="ENGLAND",
        )
        id2 = _get_deterministic_simulation_id(
            SimulationType.ECONOMY,
            model_version_id,
            policy_id,
            dynamic_id,
            dataset_id=dataset_id,
            filter_field="state_code",
            filter_value="ENGLAND",
        )

        # Then
        assert id1 != id2

    def test_given_different_filter_value_then_different_id(self):
        """Given different filter_value, then a different ID is returned."""
        # Given
        dataset_id = uuid4()
        model_version_id = uuid4()
        policy_id = None
        dynamic_id = None

        # When
        id1 = _get_deterministic_simulation_id(
            SimulationType.ECONOMY,
            model_version_id,
            policy_id,
            dynamic_id,
            dataset_id=dataset_id,
            filter_field="country",
            filter_value="ENGLAND",
        )
        id2 = _get_deterministic_simulation_id(
            SimulationType.ECONOMY,
            model_version_id,
            policy_id,
            dynamic_id,
            dataset_id=dataset_id,
            filter_field="country",
            filter_value="SCOTLAND",
        )

        # Then
        assert id1 != id2

    def test_given_filter_none_vs_filter_set_then_different_id(self):
        """Given None filter vs set filter, then different IDs are returned."""
        # Given
        dataset_id = uuid4()
        model_version_id = uuid4()
        policy_id = None
        dynamic_id = None

        # When
        id_no_filter = _get_deterministic_simulation_id(
            SimulationType.ECONOMY,
            model_version_id,
            policy_id,
            dynamic_id,
            dataset_id=dataset_id,
            filter_field=None,
            filter_value=None,
        )
        id_with_filter = _get_deterministic_simulation_id(
            SimulationType.ECONOMY,
            model_version_id,
            policy_id,
            dynamic_id,
            dataset_id=dataset_id,
            filter_field="country",
            filter_value="ENGLAND",
        )

        # Then
        assert id_no_filter != id_with_filter

    def test_given_different_dataset_then_different_id(self):
        """Given different dataset_id, then a different ID is returned."""
        # Given
        model_version_id = uuid4()
        policy_id = None
        dynamic_id = None
        filter_field = "country"
        filter_value = "ENGLAND"

        # When
        id1 = _get_deterministic_simulation_id(
            SimulationType.ECONOMY,
            model_version_id,
            policy_id,
            dynamic_id,
            dataset_id=uuid4(),
            filter_field=filter_field,
            filter_value=filter_value,
        )
        id2 = _get_deterministic_simulation_id(
            SimulationType.ECONOMY,
            model_version_id,
            policy_id,
            dynamic_id,
            dataset_id=uuid4(),
            filter_field=filter_field,
            filter_value=filter_value,
        )

        # Then
        assert id1 != id2

    def test_given_null_optional_params_then_consistent_id(self):
        """Given null optional parameters, then consistent ID is generated."""
        # Given
        dataset_id = uuid4()
        model_version_id = uuid4()

        # When
        id1 = _get_deterministic_simulation_id(
            SimulationType.ECONOMY,
            model_version_id,
            None,
            None,
            dataset_id=dataset_id,
            filter_field=None,
            filter_value=None,
        )
        id2 = _get_deterministic_simulation_id(
            SimulationType.ECONOMY,
            model_version_id,
            None,
            None,
            dataset_id=dataset_id,
            filter_field=None,
            filter_value=None,
        )

        # Then
        assert id1 == id2
