"""Tests for _build_response() and _safe_float() in analysis.py.

Covers all Phase 2 output fields: poverty, inequality, budget_summary,
intra_decile, program_statistics, detailed_budget, and decile_impacts.
"""

import math

from policyengine_api.api.analysis import _build_response, _safe_float
from policyengine_api.models import ReportStatus
from test_fixtures.fixtures_economic_impact_response import (
    BUDGET_VARIABLES_UK,
    INTRA_DECILE_DECILE_COUNT,
    SAMPLE_BOTTOM_50_SHARE,
    SAMPLE_GINI,
    SAMPLE_INEQUALITY_INCOME_VAR,
    SAMPLE_POVERTY_TYPES,
    SAMPLE_TOP_1_SHARE,
    SAMPLE_TOP_10_SHARE,
    UK_PROGRAM_COUNT,
    UK_PROGRAMS,
    add_budget_summary_records,
    add_inequality_records,
    add_intra_decile_records,
    add_poverty_by_age_records,
    add_poverty_records,
    add_program_statistics_records,
    create_fully_populated_report,
    create_report_with_simulations,
)


# ---------------------------------------------------------------------------
# _safe_float
# ---------------------------------------------------------------------------


class TestSafeFloat:
    """Tests for the _safe_float helper that sanitizes floats for JSON."""

    def test__given_normal_float__then_returns_same_value(self):
        assert _safe_float(42.5) == 42.5

    def test__given_none__then_returns_none(self):
        assert _safe_float(None) is None

    def test__given_nan__then_returns_none(self):
        assert _safe_float(float("nan")) is None

    def test__given_positive_inf__then_returns_none(self):
        assert _safe_float(float("inf")) is None

    def test__given_negative_inf__then_returns_none(self):
        assert _safe_float(float("-inf")) is None

    def test__given_zero__then_returns_zero(self):
        assert _safe_float(0.0) == 0.0

    def test__given_negative_float__then_returns_same_value(self):
        assert _safe_float(-123.456) == -123.456


# ---------------------------------------------------------------------------
# _build_response — pending report
# ---------------------------------------------------------------------------


class TestBuildResponsePending:
    """Tests for _build_response when the report is not yet completed."""

    def test__given_pending_report__then_all_output_fields_are_none(self, session):
        # Given
        report, baseline_sim, reform_sim = create_report_with_simulations(
            session, status=ReportStatus.PENDING
        )

        # When
        response = _build_response(report, baseline_sim, reform_sim, session)

        # Then
        assert response.status == ReportStatus.PENDING
        assert response.decile_impacts is None
        assert response.program_statistics is None
        assert response.poverty is None
        assert response.inequality is None
        assert response.budget_summary is None
        assert response.intra_decile is None
        assert response.detailed_budget is None

    def test__given_running_report__then_all_output_fields_are_none(self, session):
        # Given
        report, baseline_sim, reform_sim = create_report_with_simulations(
            session, status=ReportStatus.RUNNING
        )

        # When
        response = _build_response(report, baseline_sim, reform_sim, session)

        # Then
        assert response.status == ReportStatus.RUNNING
        assert response.poverty is None
        assert response.inequality is None


# ---------------------------------------------------------------------------
# _build_response — poverty
# ---------------------------------------------------------------------------


class TestBuildResponsePoverty:
    """Tests for poverty records in _build_response output."""

    def test__given_completed_report_with_poverty__then_poverty_list_not_empty(
        self, session
    ):
        # Given
        report, baseline_sim, reform_sim = create_report_with_simulations(session)
        add_poverty_records(session, report, baseline_sim, reform_sim)

        # When
        response = _build_response(report, baseline_sim, reform_sim, session)

        # Then
        assert response.poverty is not None
        assert len(response.poverty) > 0

    def test__given_poverty_records__then_each_has_poverty_type(self, session):
        # Given
        report, baseline_sim, reform_sim = create_report_with_simulations(session)
        add_poverty_records(session, report, baseline_sim, reform_sim)

        # When
        response = _build_response(report, baseline_sim, reform_sim, session)

        # Then
        for p in response.poverty:
            assert p.poverty_type in SAMPLE_POVERTY_TYPES

    def test__given_poverty_by_age_records__then_filter_variable_is_set(self, session):
        # Given
        report, baseline_sim, reform_sim = create_report_with_simulations(session)
        add_poverty_by_age_records(session, report, baseline_sim, reform_sim)

        # When
        response = _build_response(report, baseline_sim, reform_sim, session)

        # Then
        assert response.poverty is not None
        filter_vars = {p.filter_variable for p in response.poverty}
        assert "is_child" in filter_vars
        assert "is_adult" in filter_vars
        assert "is_SP_age" in filter_vars

    def test__given_poverty_records__then_rate_is_headcount_over_population(
        self, session
    ):
        # Given
        report, baseline_sim, reform_sim = create_report_with_simulations(session)
        add_poverty_records(session, report, baseline_sim, reform_sim)

        # When
        response = _build_response(report, baseline_sim, reform_sim, session)

        # Then
        for p in response.poverty:
            expected_rate = p.headcount / p.total_population
            assert abs(p.rate - expected_rate) < 1e-9


# ---------------------------------------------------------------------------
# _build_response — inequality
# ---------------------------------------------------------------------------


class TestBuildResponseInequality:
    """Tests for inequality records in _build_response output."""

    def test__given_completed_report_with_inequality__then_two_records(self, session):
        # Given — one for baseline, one for reform
        report, baseline_sim, reform_sim = create_report_with_simulations(session)
        add_inequality_records(session, report, baseline_sim, reform_sim)

        # When
        response = _build_response(report, baseline_sim, reform_sim, session)

        # Then
        assert response.inequality is not None
        assert len(response.inequality) == 2

    def test__given_inequality_records__then_gini_matches_input(self, session):
        # Given
        report, baseline_sim, reform_sim = create_report_with_simulations(session)
        add_inequality_records(session, report, baseline_sim, reform_sim)

        # When
        response = _build_response(report, baseline_sim, reform_sim, session)

        # Then
        for ineq in response.inequality:
            assert ineq.gini == SAMPLE_GINI
            assert ineq.top_10_share == SAMPLE_TOP_10_SHARE
            assert ineq.top_1_share == SAMPLE_TOP_1_SHARE
            assert ineq.bottom_50_share == SAMPLE_BOTTOM_50_SHARE

    def test__given_inequality_records__then_income_variable_set(self, session):
        # Given
        report, baseline_sim, reform_sim = create_report_with_simulations(session)
        add_inequality_records(session, report, baseline_sim, reform_sim)

        # When
        response = _build_response(report, baseline_sim, reform_sim, session)

        # Then
        for ineq in response.inequality:
            assert ineq.income_variable == SAMPLE_INEQUALITY_INCOME_VAR


# ---------------------------------------------------------------------------
# _build_response — budget_summary
# ---------------------------------------------------------------------------


class TestBuildResponseBudgetSummary:
    """Tests for budget_summary records in _build_response output."""

    def test__given_completed_report_with_budget__then_correct_count(self, session):
        # Given
        report, baseline_sim, reform_sim = create_report_with_simulations(session)
        add_budget_summary_records(session, report, baseline_sim, reform_sim)

        # When
        response = _build_response(report, baseline_sim, reform_sim, session)

        # Then
        assert response.budget_summary is not None
        assert len(response.budget_summary) == len(BUDGET_VARIABLES_UK)

    def test__given_budget_records__then_change_equals_reform_minus_baseline(
        self, session
    ):
        # Given
        report, baseline_sim, reform_sim = create_report_with_simulations(session)
        add_budget_summary_records(session, report, baseline_sim, reform_sim)

        # When
        response = _build_response(report, baseline_sim, reform_sim, session)

        # Then
        for b in response.budget_summary:
            expected_change = b.reform_total - b.baseline_total
            assert abs(b.change - expected_change) < 1e-9

    def test__given_budget_records__then_variable_names_match_uk_set(self, session):
        # Given
        report, baseline_sim, reform_sim = create_report_with_simulations(session)
        add_budget_summary_records(session, report, baseline_sim, reform_sim)

        # When
        response = _build_response(report, baseline_sim, reform_sim, session)

        # Then
        var_names = {b.variable_name for b in response.budget_summary}
        expected_names = {name for name, _ in BUDGET_VARIABLES_UK}
        assert var_names == expected_names


# ---------------------------------------------------------------------------
# _build_response — intra_decile
# ---------------------------------------------------------------------------


class TestBuildResponseIntraDecile:
    """Tests for intra_decile records in _build_response output."""

    def test__given_completed_report_with_intra_decile__then_11_records(self, session):
        # Given
        report, baseline_sim, reform_sim = create_report_with_simulations(session)
        add_intra_decile_records(session, report, baseline_sim, reform_sim)

        # When
        response = _build_response(report, baseline_sim, reform_sim, session)

        # Then
        assert response.intra_decile is not None
        assert len(response.intra_decile) == INTRA_DECILE_DECILE_COUNT

    def test__given_intra_decile_records__then_decile_0_present_for_overall(
        self, session
    ):
        # Given
        report, baseline_sim, reform_sim = create_report_with_simulations(session)
        add_intra_decile_records(session, report, baseline_sim, reform_sim)

        # When
        response = _build_response(report, baseline_sim, reform_sim, session)

        # Then
        decile_numbers = {r.decile for r in response.intra_decile}
        assert 0 in decile_numbers  # overall row

    def test__given_intra_decile_records__then_proportions_sum_to_one(self, session):
        # Given
        report, baseline_sim, reform_sim = create_report_with_simulations(session)
        add_intra_decile_records(session, report, baseline_sim, reform_sim)

        # When
        response = _build_response(report, baseline_sim, reform_sim, session)

        # Then
        for r in response.intra_decile:
            total = (
                r.lose_more_than_5pct
                + r.lose_less_than_5pct
                + r.no_change
                + r.gain_less_than_5pct
                + r.gain_more_than_5pct
            )
            assert abs(total - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# _build_response — program_statistics & detailed_budget
# ---------------------------------------------------------------------------


class TestBuildResponseProgramStatistics:
    """Tests for program_statistics and detailed_budget in _build_response."""

    def test__given_completed_report_with_programs__then_correct_count(self, session):
        # Given
        report, baseline_sim, reform_sim = create_report_with_simulations(session)
        add_program_statistics_records(session, report, baseline_sim, reform_sim)

        # When
        response = _build_response(report, baseline_sim, reform_sim, session)

        # Then
        assert response.program_statistics is not None
        assert len(response.program_statistics) == UK_PROGRAM_COUNT

    def test__given_uk_programs__then_all_10_programs_present(self, session):
        # Given
        report, baseline_sim, reform_sim = create_report_with_simulations(session)
        add_program_statistics_records(session, report, baseline_sim, reform_sim)

        # When
        response = _build_response(report, baseline_sim, reform_sim, session)

        # Then
        program_names = {s.program_name for s in response.program_statistics}
        assert program_names == set(UK_PROGRAMS.keys())

    def test__given_program_records__then_detailed_budget_has_same_keys(self, session):
        # Given
        report, baseline_sim, reform_sim = create_report_with_simulations(session)
        add_program_statistics_records(session, report, baseline_sim, reform_sim)

        # When
        response = _build_response(report, baseline_sim, reform_sim, session)

        # Then
        assert response.detailed_budget is not None
        assert set(response.detailed_budget.keys()) == set(UK_PROGRAMS.keys())

    def test__given_program_records__then_detailed_budget_has_baseline_reform_difference(
        self, session
    ):
        # Given
        report, baseline_sim, reform_sim = create_report_with_simulations(session)
        add_program_statistics_records(session, report, baseline_sim, reform_sim)

        # When
        response = _build_response(report, baseline_sim, reform_sim, session)

        # Then
        for prog_name, entry in response.detailed_budget.items():
            assert "baseline" in entry
            assert "reform" in entry
            assert "difference" in entry

    def test__given_program_records__then_detailed_budget_difference_matches_change(
        self, session
    ):
        # Given
        report, baseline_sim, reform_sim = create_report_with_simulations(session)
        add_program_statistics_records(session, report, baseline_sim, reform_sim)

        # When
        response = _build_response(report, baseline_sim, reform_sim, session)

        # Then — difference should equal reform - baseline (from ProgramStatistics.change)
        for prog_name, entry in response.detailed_budget.items():
            expected_diff = entry["reform"] - entry["baseline"]
            assert abs(entry["difference"] - expected_diff) < 1e-9

    def test__given_no_program_records__then_detailed_budget_is_empty_dict(
        self, session
    ):
        # Given — completed report with no program statistics
        report, baseline_sim, reform_sim = create_report_with_simulations(session)

        # When
        response = _build_response(report, baseline_sim, reform_sim, session)

        # Then
        assert response.detailed_budget == {}

    def test__given_program_with_nan_values__then_detailed_budget_has_none(
        self, session
    ):
        # Given
        from policyengine_api.models import ProgramStatistics

        report, baseline_sim, reform_sim = create_report_with_simulations(session)
        rec = ProgramStatistics(
            baseline_simulation_id=baseline_sim.id,
            reform_simulation_id=reform_sim.id,
            report_id=report.id,
            program_name="test_program",
            entity="person",
            is_tax=True,
            baseline_total=float("nan"),
            reform_total=float("nan"),
            change=float("nan"),
            baseline_count=0.0,
            reform_count=0.0,
            winners=0.0,
            losers=0.0,
        )
        session.add(rec)
        session.commit()

        # When
        response = _build_response(report, baseline_sim, reform_sim, session)

        # Then
        assert response.detailed_budget["test_program"]["baseline"] is None
        assert response.detailed_budget["test_program"]["reform"] is None
        assert response.detailed_budget["test_program"]["difference"] is None


# ---------------------------------------------------------------------------
# _build_response — fully populated report
# ---------------------------------------------------------------------------


class TestBuildResponseFullyPopulated:
    """Tests for _build_response with all output tables populated."""

    def test__given_fully_populated_report__then_all_fields_present(self, session):
        # Given
        report, baseline_sim, reform_sim = create_fully_populated_report(session)

        # When
        response = _build_response(report, baseline_sim, reform_sim, session)

        # Then
        assert response.status == ReportStatus.COMPLETED
        assert response.poverty is not None
        assert response.inequality is not None
        assert response.budget_summary is not None
        assert response.intra_decile is not None
        assert response.program_statistics is not None
        assert response.detailed_budget is not None

    def test__given_fully_populated_report__then_report_id_matches(self, session):
        # Given
        report, baseline_sim, reform_sim = create_fully_populated_report(session)

        # When
        response = _build_response(report, baseline_sim, reform_sim, session)

        # Then
        assert response.report_id == report.id

    def test__given_fully_populated_report__then_simulation_ids_match(self, session):
        # Given
        report, baseline_sim, reform_sim = create_fully_populated_report(session)

        # When
        response = _build_response(report, baseline_sim, reform_sim, session)

        # Then
        assert response.baseline_simulation.id == baseline_sim.id
        assert response.reform_simulation.id == reform_sim.id
