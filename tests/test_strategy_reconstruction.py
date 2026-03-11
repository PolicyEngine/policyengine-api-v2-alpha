"""Tests for strategy reconstruction utility.

Tests for policyengine_api.utils.strategy_reconstruction.reconstruct_strategy(),
which rebuilds policyengine.py ScopingStrategy objects from DB columns.

The scoping_strategy module may not exist in the published policyengine package,
so we provide mock strategy classes and inject them into sys.modules when needed.
"""

import sys
from types import ModuleType

import pytest

from policyengine_api.utils.strategy_reconstruction import (
    WEIGHT_MATRIX_CONFIG,
    reconstruct_strategy,
)
from test_fixtures.fixtures_strategy_reconstruction import (
    EXPECTED_CONSTITUENCY_CONFIG,
    EXPECTED_LOCAL_AUTHORITY_CONFIG,
    FILTER_FIELDS,
    FILTER_STRATEGIES,
    FILTER_VALUES,
    REGION_TYPES,
)

# ---------------------------------------------------------------------------
# Mock strategy classes (match the real constructor signatures)
# ---------------------------------------------------------------------------


class _MockRowFilterStrategy:
    strategy_type = "row_filter"

    def __init__(self, *, variable_name: str, variable_value: str):
        self.variable_name = variable_name
        self.variable_value = variable_value


class _MockWeightReplacementStrategy:
    strategy_type = "weight_replacement"

    def __init__(
        self,
        *,
        region_code: str,
        weight_matrix_bucket: str,
        weight_matrix_key: str,
        lookup_csv_bucket: str,
        lookup_csv_key: str,
    ):
        self.region_code = region_code
        self.weight_matrix_bucket = weight_matrix_bucket
        self.weight_matrix_key = weight_matrix_key
        self.lookup_csv_bucket = lookup_csv_bucket
        self.lookup_csv_key = lookup_csv_key


@pytest.fixture(autouse=True)
def _ensure_scoping_strategy_module(monkeypatch):
    """Inject a mock scoping_strategy module if the real one is not installed."""
    try:
        from policyengine.core.scoping_strategy import (  # noqa: F401
            RowFilterStrategy,
            WeightReplacementStrategy,
        )
    except (ImportError, ModuleNotFoundError):
        mock_mod = ModuleType("policyengine.core.scoping_strategy")
        mock_mod.RowFilterStrategy = _MockRowFilterStrategy  # type: ignore[attr-defined]
        mock_mod.WeightReplacementStrategy = _MockWeightReplacementStrategy  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "policyengine.core.scoping_strategy", mock_mod)


# ---------------------------------------------------------------------------
# reconstruct_strategy — None / no-op cases
# ---------------------------------------------------------------------------


class TestReconstructStrategyNone:
    """Tests for cases where reconstruct_strategy returns None."""

    def test__given_none_filter_strategy__then_returns_none(self):
        # Given
        filter_strategy = None

        # When
        result = reconstruct_strategy(
            filter_strategy=filter_strategy,
            filter_field=FILTER_FIELDS["COUNTRY"],
            filter_value=FILTER_VALUES["ENGLAND"],
            region_type=REGION_TYPES["COUNTRY"],
        )

        # Then
        assert result is None

    def test__given_row_filter_without_filter_field__then_returns_none(self):
        # Given
        filter_field = None

        # When
        result = reconstruct_strategy(
            filter_strategy=FILTER_STRATEGIES["ROW_FILTER"],
            filter_field=filter_field,
            filter_value=FILTER_VALUES["ENGLAND"],
            region_type=REGION_TYPES["COUNTRY"],
        )

        # Then
        assert result is None

    def test__given_row_filter_without_filter_value__then_returns_none(self):
        # Given
        filter_value = None

        # When
        result = reconstruct_strategy(
            filter_strategy=FILTER_STRATEGIES["ROW_FILTER"],
            filter_field=FILTER_FIELDS["COUNTRY"],
            filter_value=filter_value,
            region_type=REGION_TYPES["COUNTRY"],
        )

        # Then
        assert result is None

    def test__given_weight_replacement_without_filter_value__then_returns_none(self):
        # Given
        filter_value = None

        # When
        result = reconstruct_strategy(
            filter_strategy=FILTER_STRATEGIES["WEIGHT_REPLACEMENT"],
            filter_field=None,
            filter_value=filter_value,
            region_type=REGION_TYPES["CONSTITUENCY"],
        )

        # Then
        assert result is None

    def test__given_weight_replacement_without_region_type__then_returns_none(self):
        # Given
        region_type = None

        # When
        result = reconstruct_strategy(
            filter_strategy=FILTER_STRATEGIES["WEIGHT_REPLACEMENT"],
            filter_field=None,
            filter_value=FILTER_VALUES["SHEFFIELD_CENTRAL"],
            region_type=region_type,
        )

        # Then
        assert result is None


# ---------------------------------------------------------------------------
# reconstruct_strategy — RowFilterStrategy
# ---------------------------------------------------------------------------


class TestReconstructStrategyRowFilter:
    """Tests for RowFilterStrategy reconstruction."""

    def test__given_row_filter_strategy__then_returns_row_filter_instance(self):
        # Given / When
        result = reconstruct_strategy(
            filter_strategy=FILTER_STRATEGIES["ROW_FILTER"],
            filter_field=FILTER_FIELDS["COUNTRY"],
            filter_value=FILTER_VALUES["ENGLAND"],
            region_type=REGION_TYPES["COUNTRY"],
        )

        # Then
        assert result.strategy_type == "row_filter"

    def test__given_row_filter_strategy__then_variable_name_matches(self):
        # Given / When
        result = reconstruct_strategy(
            filter_strategy=FILTER_STRATEGIES["ROW_FILTER"],
            filter_field=FILTER_FIELDS["COUNTRY"],
            filter_value=FILTER_VALUES["ENGLAND"],
            region_type=REGION_TYPES["COUNTRY"],
        )

        # Then
        assert result.variable_name == FILTER_FIELDS["COUNTRY"]

    def test__given_row_filter_strategy__then_variable_value_matches(self):
        # Given / When
        result = reconstruct_strategy(
            filter_strategy=FILTER_STRATEGIES["ROW_FILTER"],
            filter_field=FILTER_FIELDS["COUNTRY"],
            filter_value=FILTER_VALUES["ENGLAND"],
            region_type=REGION_TYPES["COUNTRY"],
        )

        # Then
        assert result.variable_value == FILTER_VALUES["ENGLAND"]

    def test__given_us_state_row_filter__then_returns_correct_strategy(self):
        # Given / When
        result = reconstruct_strategy(
            filter_strategy=FILTER_STRATEGIES["ROW_FILTER"],
            filter_field=FILTER_FIELDS["STATE_CODE"],
            filter_value=FILTER_VALUES["CALIFORNIA"],
            region_type=REGION_TYPES["STATE"],
        )

        # Then
        assert result.strategy_type == "row_filter"
        assert result.variable_name == FILTER_FIELDS["STATE_CODE"]
        assert result.variable_value == FILTER_VALUES["CALIFORNIA"]

    def test__given_place_fips_row_filter__then_returns_correct_strategy(self):
        # Given
        fips_value = "44000"

        # When
        result = reconstruct_strategy(
            filter_strategy=FILTER_STRATEGIES["ROW_FILTER"],
            filter_field=FILTER_FIELDS["PLACE_FIPS"],
            filter_value=fips_value,
            region_type=REGION_TYPES["STATE"],
        )

        # Then
        assert result.strategy_type == "row_filter"
        assert result.variable_name == FILTER_FIELDS["PLACE_FIPS"]
        assert result.variable_value == fips_value


# ---------------------------------------------------------------------------
# reconstruct_strategy — WeightReplacementStrategy
# ---------------------------------------------------------------------------


class TestReconstructStrategyWeightReplacement:
    """Tests for WeightReplacementStrategy reconstruction."""

    def test__given_constituency_weight_replacement__then_returns_weight_replacement_instance(
        self,
    ):
        # Given / When
        result = reconstruct_strategy(
            filter_strategy=FILTER_STRATEGIES["WEIGHT_REPLACEMENT"],
            filter_field=None,
            filter_value=FILTER_VALUES["SHEFFIELD_CENTRAL"],
            region_type=REGION_TYPES["CONSTITUENCY"],
        )

        # Then
        assert result.strategy_type == "weight_replacement"

    def test__given_constituency_weight_replacement__then_region_code_matches(self):
        # Given / When
        result = reconstruct_strategy(
            filter_strategy=FILTER_STRATEGIES["WEIGHT_REPLACEMENT"],
            filter_field=None,
            filter_value=FILTER_VALUES["SHEFFIELD_CENTRAL"],
            region_type=REGION_TYPES["CONSTITUENCY"],
        )

        # Then
        assert result.region_code == FILTER_VALUES["SHEFFIELD_CENTRAL"]

    def test__given_constituency_weight_replacement__then_gcs_config_matches(self):
        # Given / When
        result = reconstruct_strategy(
            filter_strategy=FILTER_STRATEGIES["WEIGHT_REPLACEMENT"],
            filter_field=None,
            filter_value=FILTER_VALUES["SHEFFIELD_CENTRAL"],
            region_type=REGION_TYPES["CONSTITUENCY"],
        )

        # Then
        assert (
            result.weight_matrix_bucket
            == EXPECTED_CONSTITUENCY_CONFIG["weight_matrix_bucket"]
        )
        assert (
            result.weight_matrix_key
            == EXPECTED_CONSTITUENCY_CONFIG["weight_matrix_key"]
        )
        assert (
            result.lookup_csv_bucket
            == EXPECTED_CONSTITUENCY_CONFIG["lookup_csv_bucket"]
        )
        assert result.lookup_csv_key == EXPECTED_CONSTITUENCY_CONFIG["lookup_csv_key"]

    def test__given_local_authority_weight_replacement__then_returns_weight_replacement_instance(
        self,
    ):
        # Given / When
        result = reconstruct_strategy(
            filter_strategy=FILTER_STRATEGIES["WEIGHT_REPLACEMENT"],
            filter_field=None,
            filter_value=FILTER_VALUES["MANCHESTER"],
            region_type=REGION_TYPES["LOCAL_AUTHORITY"],
        )

        # Then
        assert result.strategy_type == "weight_replacement"

    def test__given_local_authority_weight_replacement__then_gcs_config_matches(self):
        # Given / When
        result = reconstruct_strategy(
            filter_strategy=FILTER_STRATEGIES["WEIGHT_REPLACEMENT"],
            filter_field=None,
            filter_value=FILTER_VALUES["MANCHESTER"],
            region_type=REGION_TYPES["LOCAL_AUTHORITY"],
        )

        # Then
        assert (
            result.weight_matrix_bucket
            == EXPECTED_LOCAL_AUTHORITY_CONFIG["weight_matrix_bucket"]
        )
        assert (
            result.weight_matrix_key
            == EXPECTED_LOCAL_AUTHORITY_CONFIG["weight_matrix_key"]
        )
        assert (
            result.lookup_csv_bucket
            == EXPECTED_LOCAL_AUTHORITY_CONFIG["lookup_csv_bucket"]
        )
        assert (
            result.lookup_csv_key == EXPECTED_LOCAL_AUTHORITY_CONFIG["lookup_csv_key"]
        )


# ---------------------------------------------------------------------------
# reconstruct_strategy — error cases
# ---------------------------------------------------------------------------


class TestReconstructStrategyErrors:
    """Tests for error handling in reconstruct_strategy."""

    def test__given_unknown_filter_strategy__then_raises_value_error(self):
        # Given
        unknown_strategy = "magic_strategy"

        # When / Then
        with pytest.raises(ValueError, match="Unknown filter_strategy"):
            reconstruct_strategy(
                filter_strategy=unknown_strategy,
                filter_field=FILTER_FIELDS["COUNTRY"],
                filter_value=FILTER_VALUES["ENGLAND"],
                region_type=REGION_TYPES["COUNTRY"],
            )

    def test__given_weight_replacement_unknown_region_type__then_raises_value_error(
        self,
    ):
        # Given
        unknown_region_type = "province"

        # When / Then
        with pytest.raises(ValueError, match="No weight matrix config"):
            reconstruct_strategy(
                filter_strategy=FILTER_STRATEGIES["WEIGHT_REPLACEMENT"],
                filter_field=None,
                filter_value=FILTER_VALUES["SHEFFIELD_CENTRAL"],
                region_type=unknown_region_type,
            )


# ---------------------------------------------------------------------------
# WEIGHT_MATRIX_CONFIG — verify expected keys exist
# ---------------------------------------------------------------------------


class TestWeightMatrixConfig:
    """Tests for the WEIGHT_MATRIX_CONFIG constant."""

    def test__given_config__then_constituency_key_exists(self):
        assert REGION_TYPES["CONSTITUENCY"] in WEIGHT_MATRIX_CONFIG

    def test__given_config__then_local_authority_key_exists(self):
        assert REGION_TYPES["LOCAL_AUTHORITY"] in WEIGHT_MATRIX_CONFIG

    def test__given_constituency_config__then_has_all_required_keys(self):
        config = WEIGHT_MATRIX_CONFIG[REGION_TYPES["CONSTITUENCY"]]
        expected_keys = {
            "weight_matrix_bucket",
            "weight_matrix_key",
            "lookup_csv_bucket",
            "lookup_csv_key",
        }
        assert set(config.keys()) == expected_keys

    def test__given_local_authority_config__then_has_all_required_keys(self):
        config = WEIGHT_MATRIX_CONFIG[REGION_TYPES["LOCAL_AUTHORITY"]]
        expected_keys = {
            "weight_matrix_bucket",
            "weight_matrix_key",
            "lookup_csv_bucket",
            "lookup_csv_key",
        }
        assert set(config.keys()) == expected_keys
