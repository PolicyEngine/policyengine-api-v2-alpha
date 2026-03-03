"""Tests for intra-decile income change computation."""

import numpy as np

from policyengine_api.api.intra_decile import (
    _income_change_corrected,
    _income_change_v1_original,
    compute_intra_decile,
    get_income_change_formula,
)
from test_fixtures.fixtures_intra_decile import (
    CATEGORY_NAMES,
    EXPECTED_DECILE_NUMBERS,
    EXPECTED_ROW_COUNT,
    make_baseline_income,
    make_household_data,
    make_single_household_arrays,
)

# ---------------------------------------------------------------------------
# Income change formula variants
# ---------------------------------------------------------------------------


class TestIncomeChangeFormulas:
    """Tests for the two income change formula variants."""

    def test__given_both_incomes_above_1__when_v1_formula__then_doubles_percentage(
        self,
    ):
        # Given
        baseline, reform = make_single_household_arrays(100.0, 103.0)

        # When
        result = _income_change_v1_original(baseline, reform)

        # Then — V1 produces ~6% instead of 3%
        assert abs(result[0] - 0.06) < 1e-9

    def test__given_both_incomes_above_1__when_corrected_formula__then_correct_percentage(
        self,
    ):
        # Given
        baseline, reform = make_single_household_arrays(100.0, 103.0)

        # When
        result = _income_change_corrected(baseline, reform)

        # Then
        assert abs(result[0] - 0.03) < 1e-9

    def test__given_zero_baseline__when_corrected_formula__then_caps_denominator_at_1(
        self,
    ):
        # Given
        baseline, reform = make_single_household_arrays(0.0, 10.0)

        # When
        result = _income_change_corrected(baseline, reform)

        # Then — denominator capped at 1, so change = (10 - 0) / 1 = 10.0
        assert abs(result[0] - 10.0) < 1e-9

    def test__given_negative_baseline__when_corrected_formula__then_caps_denominator_at_1(
        self,
    ):
        # Given
        baseline, reform = make_single_household_arrays(-5.0, 5.0)

        # When
        result = _income_change_corrected(baseline, reform)

        # Then — denominator capped at 1, change = (5 - (-5)) / 1 = 10.0
        assert abs(result[0] - 10.0) < 1e-9

    def test__given_identical_incomes__when_v1_formula__then_zero_change(self):
        # Given
        baseline, reform = make_single_household_arrays(50_000.0, 50_000.0)

        # When
        result = _income_change_v1_original(baseline, reform)

        # Then
        assert result[0] == 0.0

    def test__given_identical_incomes__when_corrected_formula__then_zero_change(self):
        # Given
        baseline, reform = make_single_household_arrays(50_000.0, 50_000.0)

        # When
        result = _income_change_corrected(baseline, reform)

        # Then
        assert result[0] == 0.0

    def test__given_strategy_selector__then_returns_corrected_formula(self):
        # When
        formula = get_income_change_formula()

        # Then
        assert formula is _income_change_corrected


# ---------------------------------------------------------------------------
# compute_intra_decile — structure
# ---------------------------------------------------------------------------


class TestComputeIntraDecileStructure:
    """Tests for the shape and structure of compute_intra_decile output."""

    def test__given_any_input__then_returns_11_rows(self):
        # Given
        income = make_baseline_income()
        baseline, reform = make_household_data(income)

        # When
        rows = compute_intra_decile(baseline, reform)

        # Then
        assert len(rows) == EXPECTED_ROW_COUNT

    def test__given_any_input__then_decile_numbers_are_1_through_10_plus_0(self):
        # Given
        income = make_baseline_income()
        baseline, reform = make_household_data(income)

        # When
        rows = compute_intra_decile(baseline, reform)
        decile_numbers = [r["decile"] for r in rows]

        # Then
        assert decile_numbers == EXPECTED_DECILE_NUMBERS

    def test__given_any_input__then_each_row_has_all_category_columns(self):
        # Given
        income = make_baseline_income()
        baseline, reform = make_household_data(income)

        # When
        rows = compute_intra_decile(baseline, reform)

        # Then
        for row in rows:
            for col in CATEGORY_NAMES:
                assert col in row, (
                    f"Missing column {col} in row for decile {row['decile']}"
                )

    def test__given_any_input__then_proportions_sum_to_approximately_one_per_decile(
        self,
    ):
        # Given — a mix of changes so multiple categories are populated
        income = make_baseline_income()
        reform_income = income * np.where(np.arange(len(income)) % 3 == 0, 1.03, 0.97)
        baseline, reform = make_household_data(income, reform_income)

        # When
        rows = compute_intra_decile(baseline, reform)

        # Then
        for row in rows:
            total = sum(row[col] for col in CATEGORY_NAMES)
            assert abs(total - 1.0) < 1e-9, (
                f"Decile {row['decile']} proportions sum to {total}, expected 1.0"
            )

    def test__given_overall_row__then_is_mean_of_decile_proportions(self):
        # Given
        income = make_baseline_income()
        baseline, reform = make_household_data(income, income * 1.03)

        # When
        rows = compute_intra_decile(baseline, reform)
        decile_rows = [r for r in rows if r["decile"] != 0]
        overall_row = [r for r in rows if r["decile"] == 0][0]

        # Then
        for col in CATEGORY_NAMES:
            expected_mean = sum(r[col] for r in decile_rows) / 10
            assert abs(overall_row[col] - expected_mean) < 1e-9


# ---------------------------------------------------------------------------
# compute_intra_decile — classification
# ---------------------------------------------------------------------------


class TestComputeIntraDecileClassification:
    """Tests for correct classification of income changes into categories."""

    def test__given_no_income_change__then_all_in_no_change_category(self):
        # Given
        income = make_baseline_income()
        baseline, reform = make_household_data(income, income)

        # When
        rows = compute_intra_decile(baseline, reform)

        # Then
        for row in rows:
            assert row["no_change"] == 1.0
            assert row["gain_less_than_5pct"] == 0.0
            assert row["gain_more_than_5pct"] == 0.0
            assert row["lose_less_than_5pct"] == 0.0
            assert row["lose_more_than_5pct"] == 0.0

    def test__given_uniform_3pct_raise__then_all_in_gain_less_than_5pct(self):
        # Given
        income = make_baseline_income()
        baseline, reform = make_household_data(income, income * 1.03)

        # When
        rows = compute_intra_decile(baseline, reform)

        # Then
        for row in rows:
            assert row["gain_less_than_5pct"] == 1.0

    def test__given_uniform_10pct_raise__then_all_in_gain_more_than_5pct(self):
        # Given
        income = make_baseline_income()
        baseline, reform = make_household_data(income, income * 1.10)

        # When
        rows = compute_intra_decile(baseline, reform)

        # Then
        for row in rows:
            assert row["gain_more_than_5pct"] == 1.0

    def test__given_uniform_3pct_loss__then_all_in_lose_less_than_5pct(self):
        # Given
        income = make_baseline_income()
        baseline, reform = make_household_data(income, income * 0.97)

        # When
        rows = compute_intra_decile(baseline, reform)

        # Then
        for row in rows:
            assert row["lose_less_than_5pct"] == 1.0

    def test__given_uniform_10pct_loss__then_all_in_lose_more_than_5pct(self):
        # Given
        income = make_baseline_income()
        baseline, reform = make_household_data(income, income * 0.90)

        # When
        rows = compute_intra_decile(baseline, reform)

        # Then
        for row in rows:
            assert row["lose_more_than_5pct"] == 1.0

    def test__given_boundary_at_exactly_5pct_gain__then_in_gain_less_than_5pct(self):
        # Given — BOUNDS uses (lower, upper], so exactly 0.05 falls in gain_less_than_5pct
        # because the gain_less_than_5pct interval is (1e-3, 0.05]
        income = make_baseline_income()
        baseline, reform = make_household_data(income, income * 1.05)

        # When
        rows = compute_intra_decile(baseline, reform)

        # Then
        for row in rows:
            assert row["gain_less_than_5pct"] == 1.0

    def test__given_boundary_at_exactly_0_1pct_gain__then_in_no_change(self):
        # Given — exactly 0.001 falls in no_change because the no_change
        # interval is (-1e-3, 1e-3] and 0.001 == 1e-3 which is the upper bound
        income = make_baseline_income()
        baseline, reform = make_household_data(income, income * 1.001)

        # When
        rows = compute_intra_decile(baseline, reform)

        # Then
        for row in rows:
            assert row["no_change"] == 1.0


# ---------------------------------------------------------------------------
# compute_intra_decile — edge cases
# ---------------------------------------------------------------------------


class TestComputeIntraDecileEdgeCases:
    """Tests for edge cases in compute_intra_decile."""

    def test__given_zero_people_in_decile__then_proportions_are_zero(self):
        # Given — remove all households from decile 5 by setting their weight to 0
        income = make_baseline_income()
        weights = np.ones(len(income)) * 100.0
        people = np.full(len(income), 2.0)
        # Decile 5 is indices 40-49
        people[40:50] = 0.0

        baseline, reform = make_household_data(
            income, income * 1.03, weights=weights, people=people
        )

        # When
        rows = compute_intra_decile(baseline, reform)

        # Then — decile 5 should have all-zero proportions
        decile_5 = [r for r in rows if r["decile"] == 5][0]
        for col in CATEGORY_NAMES:
            assert decile_5[col] == 0.0
