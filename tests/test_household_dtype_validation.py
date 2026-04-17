"""Regression tests for household mixed-dtype validation (#271)."""

import pytest

from policyengine_api.api.household import (
    _assert_consistent_value,
    _default_for_dtype,
)
from policyengine_api.services.household_type_validation import (
    validate_entity_values,
)


class TestDefaultForDtype:
    def test_int_default_is_zero_float(self):
        assert _default_for_dtype(42) == 0.0

    def test_float_default_is_zero_float(self):
        assert _default_for_dtype(3.14) == 0.0

    def test_str_default_is_empty_string(self):
        assert _default_for_dtype("CA") == ""

    def test_bool_default_is_false(self):
        assert _default_for_dtype(True) is False

    def test_none_falls_back_to_numeric(self):
        assert _default_for_dtype(None) == 0.0


class TestAssertConsistentValue:
    def test_string_column_rejects_numeric(self):
        with pytest.raises(ValueError):
            _assert_consistent_value("people", "state_code", "", 42)

    def test_string_column_accepts_string(self):
        # Should not raise
        _assert_consistent_value("people", "state_code", "", "CA")

    def test_numeric_column_rejects_string(self):
        with pytest.raises(ValueError):
            _assert_consistent_value("people", "age", 0.0, "forty")

    def test_numeric_column_accepts_int_float_bool(self):
        _assert_consistent_value("people", "age", 0.0, 40)
        _assert_consistent_value("people", "age", 0.0, 40.5)
        _assert_consistent_value("people", "age", 0.0, True)

    def test_none_is_always_accepted(self):
        _assert_consistent_value("people", "x", 0.0, None)
        _assert_consistent_value("people", "x", "", None)


class TestValidateEntityValues:
    def test_type_mismatch_raises_422(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            validate_entity_values("people", [{"age": "forty"}], {"age": "int"})
        assert exc.value.status_code == 422

    def test_enum_accepts_string(self):
        validate_entity_values(
            "tax_unit", [{"state_code": "CA"}], {"state_code": "Enum"}
        )

    def test_unknown_variable_skipped(self):
        # Unknown variables are left to the simulation kernel to report.
        validate_entity_values("people", [{"weird_var": 1}], {})
