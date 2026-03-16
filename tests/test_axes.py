"""Tests for household axes utility functions."""

import pytest

from policyengine_api.utils.axes import (
    expand_dataframes_for_axes,
    reshape_axes_output,
    validate_axes,
)


class TestValidateAxes:
    """Tests for validate_axes()."""

    def test_valid_single_axis(self):
        axes = [
            [
                {
                    "name": "employment_income",
                    "min": 0,
                    "max": 100000,
                    "count": 5,
                    "index": 0,
                }
            ]
        ]
        validate_axes(axes, n_people=1)  # Should not raise

    def test_valid_parallel_axes(self):
        axes = [
            [
                {
                    "name": "employment_income",
                    "min": 0,
                    "max": 100000,
                    "count": 5,
                    "index": 0,
                },
                {
                    "name": "self_employment_income",
                    "min": 0,
                    "max": 50000,
                    "count": 5,
                    "index": 0,
                },
            ]
        ]
        validate_axes(axes, n_people=1)  # Should not raise

    def test_empty_axes(self):
        with pytest.raises(ValueError, match="exactly 1 axis group, got 0"):
            validate_axes([], n_people=1)

    def test_multiple_groups(self):
        group = [
            {
                "name": "employment_income",
                "min": 0,
                "max": 100000,
                "count": 5,
                "index": 0,
            }
        ]
        with pytest.raises(ValueError, match="exactly 1 axis group, got 2"):
            validate_axes([group, group], n_people=1)

    def test_count_too_low(self):
        axes = [
            [
                {
                    "name": "employment_income",
                    "min": 0,
                    "max": 100000,
                    "count": 1,
                    "index": 0,
                }
            ]
        ]
        with pytest.raises(ValueError, match="between 2 and 1000"):
            validate_axes(axes, n_people=1)

    def test_count_too_high(self):
        axes = [
            [
                {
                    "name": "employment_income",
                    "min": 0,
                    "max": 100000,
                    "count": 1001,
                    "index": 0,
                }
            ]
        ]
        with pytest.raises(ValueError, match="between 2 and 1000"):
            validate_axes(axes, n_people=1)

    def test_index_out_of_bounds(self):
        axes = [
            [
                {
                    "name": "employment_income",
                    "min": 0,
                    "max": 100000,
                    "count": 5,
                    "index": 2,
                }
            ]
        ]
        with pytest.raises(ValueError, match="index"):
            validate_axes(axes, n_people=2)

    def test_index_negative(self):
        axes = [
            [
                {
                    "name": "employment_income",
                    "min": 0,
                    "max": 100000,
                    "count": 5,
                    "index": -1,
                }
            ]
        ]
        with pytest.raises(ValueError, match="index"):
            validate_axes(axes, n_people=1)

    def test_mismatched_counts(self):
        axes = [
            [
                {
                    "name": "employment_income",
                    "min": 0,
                    "max": 100000,
                    "count": 5,
                    "index": 0,
                },
                {
                    "name": "self_employment_income",
                    "min": 0,
                    "max": 50000,
                    "count": 10,
                    "index": 0,
                },
            ]
        ]
        with pytest.raises(ValueError, match="same count"):
            validate_axes(axes, n_people=1)

    def test_empty_name(self):
        axes = [[{"name": "", "min": 0, "max": 100000, "count": 5, "index": 0}]]
        with pytest.raises(ValueError, match="non-empty 'name'"):
            validate_axes(axes, n_people=1)

    def test_empty_group(self):
        with pytest.raises(ValueError, match="at least one axis"):
            validate_axes([[]], n_people=1)


class TestExpandDataframes:
    """Tests for expand_dataframes_for_axes()."""

    def test_single_person_single_axis(self):
        axes = [
            [
                {
                    "name": "employment_income",
                    "min": 0,
                    "max": 1000,
                    "count": 5,
                    "index": 0,
                }
            ]
        ]
        person_data = {
            "person_id": [0],
            "person_household_id": [0],
            "person_weight": [1.0],
            "employment_income": [50000.0],
        }
        entity_datas = {
            "household": {
                "household_id": [0],
                "household_weight": [1.0],
            }
        }
        person_entity_id_keys = {"household": "person_household_id"}

        exp_person, exp_entities, count = expand_dataframes_for_axes(
            axes, person_data, entity_datas, person_entity_id_keys
        )

        assert count == 5
        assert len(exp_person["person_id"]) == 5
        assert exp_person["person_id"] == [0, 1, 2, 3, 4]
        # employment_income should be linspace(0, 1000, 5)
        assert exp_person["employment_income"] == [0.0, 250.0, 500.0, 750.0, 1000.0]
        assert exp_person["person_weight"] == [1.0] * 5

        # Household should be replicated
        assert len(exp_entities["household"]["household_id"]) == 5
        assert exp_entities["household"]["household_id"] == [0, 1, 2, 3, 4]

    def test_two_person_vary_first(self):
        axes = [
            [
                {
                    "name": "employment_income",
                    "min": 0,
                    "max": 400,
                    "count": 3,
                    "index": 0,
                }
            ]
        ]
        person_data = {
            "person_id": [0, 1],
            "person_household_id": [0, 0],
            "person_weight": [1.0, 1.0],
            "employment_income": [50000.0, 30000.0],
            "age": [40.0, 30.0],
        }
        entity_datas = {
            "household": {
                "household_id": [0],
                "household_weight": [1.0],
            }
        }
        person_entity_id_keys = {"household": "person_household_id"}

        exp_person, exp_entities, count = expand_dataframes_for_axes(
            axes, person_data, entity_datas, person_entity_id_keys
        )

        assert count == 3
        # 2 people * 3 steps = 6 person rows
        assert len(exp_person["person_id"]) == 6
        assert exp_person["person_id"] == [0, 1, 2, 3, 4, 5]

        # Person 0 copies: indices 0,1,2 -> employment_income = linspace(0,400,3)
        assert exp_person["employment_income"][0] == 0.0
        assert exp_person["employment_income"][1] == 200.0
        assert exp_person["employment_income"][2] == 400.0

        # Person 1 copies: indices 3,4,5 -> employment_income stays at 30000
        assert exp_person["employment_income"][3] == 30000.0
        assert exp_person["employment_income"][4] == 30000.0
        assert exp_person["employment_income"][5] == 30000.0

        # Age should be replicated
        assert exp_person["age"][0:3] == [40.0, 40.0, 40.0]
        assert exp_person["age"][3:6] == [30.0, 30.0, 30.0]

    def test_entity_replication(self):
        axes = [
            [
                {
                    "name": "employment_income",
                    "min": 0,
                    "max": 100,
                    "count": 3,
                    "index": 0,
                }
            ]
        ]
        person_data = {
            "person_id": [0],
            "person_benunit_id": [0],
            "person_household_id": [0],
            "person_weight": [1.0],
        }
        entity_datas = {
            "benunit": {
                "benunit_id": [0],
                "benunit_weight": [1.0],
            },
            "household": {
                "household_id": [0],
                "household_weight": [1.0],
                "region": ["LONDON"],
            },
        }
        person_entity_id_keys = {
            "benunit": "person_benunit_id",
            "household": "person_household_id",
        }

        exp_person, exp_entities, count = expand_dataframes_for_axes(
            axes, person_data, entity_datas, person_entity_id_keys
        )

        assert count == 3

        # Benunit replicated
        assert len(exp_entities["benunit"]["benunit_id"]) == 3
        assert exp_entities["benunit"]["benunit_id"] == [0, 1, 2]

        # Household replicated with region
        assert len(exp_entities["household"]["household_id"]) == 3
        assert exp_entities["household"]["region"] == ["LONDON", "LONDON", "LONDON"]

        # FK mapping updated
        assert exp_person["person_benunit_id"] == [0, 1, 2]
        assert exp_person["person_household_id"] == [0, 1, 2]

    def test_parallel_axes(self):
        axes = [
            [
                {
                    "name": "employment_income",
                    "min": 0,
                    "max": 1000,
                    "count": 3,
                    "index": 0,
                },
                {
                    "name": "self_employment_income",
                    "min": 100,
                    "max": 500,
                    "count": 3,
                    "index": 0,
                },
            ]
        ]
        person_data = {
            "person_id": [0],
            "person_household_id": [0],
            "person_weight": [1.0],
        }
        entity_datas = {
            "household": {
                "household_id": [0],
                "household_weight": [1.0],
            }
        }
        person_entity_id_keys = {"household": "person_household_id"}

        exp_person, exp_entities, count = expand_dataframes_for_axes(
            axes, person_data, entity_datas, person_entity_id_keys
        )

        assert count == 3
        assert exp_person["employment_income"] == [0.0, 500.0, 1000.0]
        assert exp_person["self_employment_income"] == [100.0, 300.0, 500.0]

    def test_variable_not_in_person_data_created(self):
        axes = [[{"name": "new_variable", "min": 0, "max": 10, "count": 3, "index": 0}]]
        person_data = {
            "person_id": [0],
            "person_household_id": [0],
            "person_weight": [1.0],
        }
        entity_datas = {
            "household": {
                "household_id": [0],
                "household_weight": [1.0],
            }
        }
        person_entity_id_keys = {"household": "person_household_id"}

        exp_person, _, _ = expand_dataframes_for_axes(
            axes, person_data, entity_datas, person_entity_id_keys
        )

        assert "new_variable" in exp_person
        assert exp_person["new_variable"] == [0.0, 5.0, 10.0]


class TestReshapeAxesOutput:
    """Tests for reshape_axes_output()."""

    def test_single_person(self):
        # 1 person * 3 steps = 3 rows
        result = {
            "person": [
                {"employment_income": 0.0, "tax": 0.0},
                {"employment_income": 500.0, "tax": 100.0},
                {"employment_income": 1000.0, "tax": 200.0},
            ],
            "household": [
                {"income": 0.0},
                {"income": 500.0},
                {"income": 1000.0},
            ],
        }
        n_original = {"person": 1, "household": 1}

        reshaped = reshape_axes_output(result, n_original, axis_count=3)

        assert len(reshaped["person"]) == 1
        assert reshaped["person"][0]["employment_income"] == [0.0, 500.0, 1000.0]
        assert reshaped["person"][0]["tax"] == [0.0, 100.0, 200.0]

        assert len(reshaped["household"]) == 1
        assert reshaped["household"][0]["income"] == [0.0, 500.0, 1000.0]

    def test_two_person(self):
        # 2 people * 2 steps = 4 rows
        result = {
            "person": [
                {"income": 0.0},
                {"income": 100.0},
                {"income": 50.0},
                {"income": 50.0},
            ],
        }
        n_original = {"person": 2}

        reshaped = reshape_axes_output(result, n_original, axis_count=2)

        assert len(reshaped["person"]) == 2
        assert reshaped["person"][0]["income"] == [0.0, 100.0]
        assert reshaped["person"][1]["income"] == [50.0, 50.0]

    def test_string_values(self):
        result = {
            "person": [
                {"status": "employed"},
                {"status": "unemployed"},
            ],
        }
        n_original = {"person": 1}

        reshaped = reshape_axes_output(result, n_original, axis_count=2)

        assert reshaped["person"][0]["status"] == ["employed", "unemployed"]

    def test_unknown_entity_passthrough(self):
        result = {
            "person": [{"income": 0.0}, {"income": 100.0}],
            "unknown_entity": [{"x": 1}],
        }
        n_original = {"person": 1}

        reshaped = reshape_axes_output(result, n_original, axis_count=2)

        # person is reshaped
        assert len(reshaped["person"]) == 1
        # unknown_entity passes through unchanged
        assert reshaped["unknown_entity"] == [{"x": 1}]

    def test_mismatched_rows_passthrough(self):
        result = {
            "person": [{"income": 0.0}, {"income": 100.0}, {"income": 200.0}],
        }
        # n_original * axis_count = 1 * 2 = 2, but we have 3 rows
        n_original = {"person": 1}

        reshaped = reshape_axes_output(result, n_original, axis_count=2)

        # Mismatched, so pass through unchanged
        assert len(reshaped["person"]) == 3

    def test_non_list_value_passthrough(self):
        result = {
            "person": [{"income": 0.0}, {"income": 100.0}],
            "metadata": "some_string",
        }
        n_original = {"person": 1}

        reshaped = reshape_axes_output(result, n_original, axis_count=2)

        assert reshaped["metadata"] == "some_string"
