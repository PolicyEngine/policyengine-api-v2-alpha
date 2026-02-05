"""Tests for policy reform conversion logic.

Tests the helper functions that convert policy objects to reform dict format
for use with Microsimulation. These are critical for fixing the bug where
reforms weren't being applied to economy-wide and household simulations.
"""

import sys
from unittest.mock import MagicMock

import pytest

# Mock modal before importing modal_app
sys.modules["modal"] = MagicMock()

from test_fixtures.fixtures_policy_reform import (
    DATETIME_POLICY,
    DATETIME_POLICY_EXPECTED,
    EMPTY_POLICY,
    HOUSEHOLD_EMPTY_POLICY_DATA,
    HOUSEHOLD_INCOMPLETE_POLICY_DATA,
    HOUSEHOLD_INCOMPLETE_POLICY_DATA_EXPECTED,
    HOUSEHOLD_NONE_POLICY_DATA,
    HOUSEHOLD_POLICY_DATA,
    HOUSEHOLD_POLICY_DATA_DATETIME,
    HOUSEHOLD_POLICY_DATA_DATETIME_EXPECTED,
    HOUSEHOLD_POLICY_DATA_EXPECTED,
    INVALID_ENTRIES_POLICY,
    INVALID_ENTRIES_POLICY_EXPECTED,
    ISO_STRING_POLICY,
    ISO_STRING_POLICY_EXPECTED,
    MERGED_EXPECTED,
    MERGED_MULTI_DATE_EXPECTED,
    MULTI_DATE_POLICY,
    MULTI_DATE_POLICY_EXPECTED,
    MULTI_PARAM_POLICY,
    MULTI_PARAM_POLICY_EXPECTED,
    NONE_PARAM_VALUES_POLICY,
    NONE_POLICY,
    REFORM_DICT_1,
    REFORM_DICT_2,
    REFORM_DICT_3,
    REFORM_DICT_4,
    SIMPLE_POLICY,
    SIMPLE_POLICY_EXPECTED,
)

# Import after mocking modal
from policyengine_api.modal_app import _merge_reform_dicts, _pe_policy_to_reform_dict


class TestPePolicyToReformDict:
    """Tests for _pe_policy_to_reform_dict function."""

    # =========================================================================
    # Given: Valid policy with single parameter
    # =========================================================================

    def test__given_simple_policy_with_date_object__then_returns_correct_reform_dict(
        self,
    ):
        """Given a policy with a single parameter using date object,
        then returns correctly formatted reform dict."""
        # When
        result = _pe_policy_to_reform_dict(SIMPLE_POLICY)

        # Then
        assert result == SIMPLE_POLICY_EXPECTED

    def test__given_policy_with_datetime_object__then_extracts_date_correctly(self):
        """Given a policy with datetime start_date (has time component),
        then extracts just the date part for the reform dict."""
        # When
        result = _pe_policy_to_reform_dict(DATETIME_POLICY)

        # Then
        assert result == DATETIME_POLICY_EXPECTED

    def test__given_policy_with_iso_string_date__then_parses_date_correctly(self):
        """Given a policy with ISO string start_date,
        then parses and extracts the date correctly."""
        # When
        result = _pe_policy_to_reform_dict(ISO_STRING_POLICY)

        # Then
        assert result == ISO_STRING_POLICY_EXPECTED

    # =========================================================================
    # Given: Policy with multiple parameters
    # =========================================================================

    def test__given_policy_with_multiple_parameters__then_includes_all_in_dict(self):
        """Given a policy with multiple parameter changes,
        then includes all parameters in the reform dict."""
        # When
        result = _pe_policy_to_reform_dict(MULTI_PARAM_POLICY)

        # Then
        assert result == MULTI_PARAM_POLICY_EXPECTED

    def test__given_policy_with_same_param_multiple_dates__then_includes_all_dates(
        self,
    ):
        """Given a policy with the same parameter changed at different dates,
        then includes all date entries for that parameter."""
        # When
        result = _pe_policy_to_reform_dict(MULTI_DATE_POLICY)

        # Then
        assert result == MULTI_DATE_POLICY_EXPECTED

    # =========================================================================
    # Given: Empty or None policy
    # =========================================================================

    def test__given_none_policy__then_returns_none(self):
        """Given None as policy,
        then returns None."""
        # When
        result = _pe_policy_to_reform_dict(NONE_POLICY)

        # Then
        assert result is None

    def test__given_policy_with_empty_parameter_values__then_returns_none(self):
        """Given a policy with empty parameter_values list,
        then returns None."""
        # When
        result = _pe_policy_to_reform_dict(EMPTY_POLICY)

        # Then
        assert result is None

    def test__given_policy_with_none_parameter_values__then_returns_none(self):
        """Given a policy with parameter_values=None,
        then returns None."""
        # When
        result = _pe_policy_to_reform_dict(NONE_PARAM_VALUES_POLICY)

        # Then
        assert result is None

    # =========================================================================
    # Given: Policy with invalid entries
    # =========================================================================

    def test__given_policy_with_invalid_entries__then_skips_invalid_keeps_valid(self):
        """Given a policy with some invalid entries (missing parameter or date),
        then skips invalid entries and keeps valid ones."""
        # When
        result = _pe_policy_to_reform_dict(INVALID_ENTRIES_POLICY)

        # Then
        assert result == INVALID_ENTRIES_POLICY_EXPECTED


class TestMergeReformDicts:
    """Tests for _merge_reform_dicts function."""

    # =========================================================================
    # Given: Two valid reform dicts
    # =========================================================================

    def test__given_two_reform_dicts__then_merges_with_second_taking_precedence(self):
        """Given two reform dicts with overlapping parameters,
        then merges them with the second dict taking precedence."""
        # When
        result = _merge_reform_dicts(REFORM_DICT_1, REFORM_DICT_2)

        # Then
        assert result == MERGED_EXPECTED

    def test__given_dicts_with_multiple_dates__then_merges_date_entries_correctly(self):
        """Given reform dicts with same parameter at multiple dates,
        then merges date entries correctly with second taking precedence."""
        # When
        result = _merge_reform_dicts(REFORM_DICT_3, REFORM_DICT_4)

        # Then
        assert result == MERGED_MULTI_DATE_EXPECTED

    # =========================================================================
    # Given: None values
    # =========================================================================

    def test__given_both_none__then_returns_none(self):
        """Given both reform dicts are None,
        then returns None."""
        # When
        result = _merge_reform_dicts(None, None)

        # Then
        assert result is None

    def test__given_first_none__then_returns_second(self):
        """Given first reform dict is None,
        then returns the second dict."""
        # When
        result = _merge_reform_dicts(None, REFORM_DICT_1)

        # Then
        assert result == REFORM_DICT_1

    def test__given_second_none__then_returns_first(self):
        """Given second reform dict is None,
        then returns the first dict."""
        # When
        result = _merge_reform_dicts(REFORM_DICT_1, None)

        # Then
        assert result == REFORM_DICT_1

    # =========================================================================
    # Given: Original dict should not be mutated
    # =========================================================================

    def test__given_two_dicts__then_does_not_mutate_original_dicts(self):
        """Given two reform dicts,
        then merging does not mutate the original dicts."""
        # Given
        original_dict1 = {"param.a": {"2024-01-01": 100}}
        original_dict2 = {"param.b": {"2024-01-01": 200}}
        dict1_copy = dict(original_dict1)
        dict2_copy = dict(original_dict2)

        # When
        _merge_reform_dicts(original_dict1, original_dict2)

        # Then
        assert original_dict1 == dict1_copy
        assert original_dict2 == dict2_copy


class TestHouseholdPolicyDataConversion:
    """Tests for the policy data conversion logic used in household calculations.

    This tests the conversion logic as it appears in _calculate_household_us
    and _calculate_household_uk functions.
    """

    def _convert_policy_data_to_reform(self, policy_data: dict | None) -> dict | None:
        """Convert policy_data (from API) to reform dict format.

        This mirrors the conversion logic in _calculate_household_us.
        """
        if not policy_data or not policy_data.get("parameter_values"):
            return None

        reform = {}
        for pv in policy_data["parameter_values"]:
            param_name = pv.get("parameter_name")
            value = pv.get("value")
            start_date = pv.get("start_date")

            if param_name and start_date:
                # Parse ISO date string to get just the date part
                if "T" in start_date:
                    date_str = start_date.split("T")[0]
                else:
                    date_str = start_date

                if param_name not in reform:
                    reform[param_name] = {}
                reform[param_name][date_str] = value

        return reform if reform else None

    # =========================================================================
    # Given: Valid policy data from API
    # =========================================================================

    def test__given_valid_policy_data__then_converts_to_reform_dict(self):
        """Given valid policy data from the API,
        then converts it to the correct reform dict format."""
        # When
        result = self._convert_policy_data_to_reform(HOUSEHOLD_POLICY_DATA)

        # Then
        assert result == HOUSEHOLD_POLICY_DATA_EXPECTED

    def test__given_policy_data_with_datetime_strings__then_extracts_date_part(self):
        """Given policy data with ISO datetime strings (with T and timezone),
        then extracts just the date part."""
        # When
        result = self._convert_policy_data_to_reform(HOUSEHOLD_POLICY_DATA_DATETIME)

        # Then
        assert result == HOUSEHOLD_POLICY_DATA_DATETIME_EXPECTED

    # =========================================================================
    # Given: Empty or None policy data
    # =========================================================================

    def test__given_none_policy_data__then_returns_none(self):
        """Given None policy data,
        then returns None."""
        # When
        result = self._convert_policy_data_to_reform(HOUSEHOLD_NONE_POLICY_DATA)

        # Then
        assert result is None

    def test__given_empty_parameter_values__then_returns_none(self):
        """Given policy data with empty parameter_values list,
        then returns None."""
        # When
        result = self._convert_policy_data_to_reform(HOUSEHOLD_EMPTY_POLICY_DATA)

        # Then
        assert result is None

    # =========================================================================
    # Given: Incomplete policy data
    # =========================================================================

    def test__given_incomplete_entries__then_skips_invalid_keeps_valid(self):
        """Given policy data with some entries missing required fields,
        then skips invalid entries and keeps valid ones."""
        # When
        result = self._convert_policy_data_to_reform(HOUSEHOLD_INCOMPLETE_POLICY_DATA)

        # Then
        assert result == HOUSEHOLD_INCOMPLETE_POLICY_DATA_EXPECTED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
