"""Tests for the composable computation module dispatch system."""

import inspect
from unittest.mock import MagicMock
from uuid import uuid4

from policyengine_api.api import computation_modules as cm
from policyengine_api.api.computation_modules import (
    UK_MODULE_DISPATCH,
    US_MODULE_DISPATCH,
    run_modules,
)
from policyengine_api.api.module_registry import MODULE_REGISTRY


class TestDispatchTables:
    """Tests for UK_MODULE_DISPATCH and US_MODULE_DISPATCH."""

    def test_uk_dispatch_keys_match_registry(self):
        """Every UK dispatch key should be a valid module in the registry."""
        for key in UK_MODULE_DISPATCH:
            assert key in MODULE_REGISTRY, f"UK dispatch key {key!r} not in registry"

    def test_us_dispatch_keys_match_registry(self):
        """Every US dispatch key should be a valid module in the registry."""
        for key in US_MODULE_DISPATCH:
            assert key in MODULE_REGISTRY, f"US dispatch key {key!r} not in registry"

    def test_uk_dispatch_covers_uk_modules(self):
        """UK dispatch should have an entry for every UK-applicable module."""
        uk_module_names = {
            name for name, mod in MODULE_REGISTRY.items() if "uk" in mod.countries
        }
        assert set(UK_MODULE_DISPATCH.keys()) == uk_module_names

    def test_us_dispatch_covers_us_modules(self):
        """US dispatch should have an entry for every US-applicable module."""
        us_module_names = {
            name for name, mod in MODULE_REGISTRY.items() if "us" in mod.countries
        }
        assert set(US_MODULE_DISPATCH.keys()) == us_module_names

    def test_all_dispatch_values_are_callable(self):
        for fn in UK_MODULE_DISPATCH.values():
            assert callable(fn)
        for fn in US_MODULE_DISPATCH.values():
            assert callable(fn)

    def test_uk_dispatch_has_9_entries(self):
        assert len(UK_MODULE_DISPATCH) == 9

    def test_us_dispatch_has_7_entries(self):
        assert len(US_MODULE_DISPATCH) == 7


class TestSharedModuleFunctions:
    """Tests that shared modules reference the same function objects."""

    def test_decile_function_shared_between_uk_and_us(self):
        assert UK_MODULE_DISPATCH["decile"] is US_MODULE_DISPATCH["decile"]
        assert UK_MODULE_DISPATCH["decile"] is cm.compute_decile_module

    def test_intra_decile_function_shared_between_uk_and_us(self):
        assert UK_MODULE_DISPATCH["intra_decile"] is US_MODULE_DISPATCH["intra_decile"]
        assert UK_MODULE_DISPATCH["intra_decile"] is cm.compute_intra_decile_module


class TestCountrySpecificFunctions:
    """Tests that UK/US specific modules use the correct country-specific functions."""

    def test_uk_program_statistics(self):
        assert (
            UK_MODULE_DISPATCH["program_statistics"]
            is cm.compute_program_statistics_module_uk
        )

    def test_us_program_statistics(self):
        assert (
            US_MODULE_DISPATCH["program_statistics"]
            is cm.compute_program_statistics_module_us
        )

    def test_uk_poverty(self):
        assert UK_MODULE_DISPATCH["poverty"] is cm.compute_poverty_module_uk

    def test_us_poverty(self):
        assert US_MODULE_DISPATCH["poverty"] is cm.compute_poverty_module_us

    def test_uk_inequality(self):
        assert UK_MODULE_DISPATCH["inequality"] is cm.compute_inequality_module_uk

    def test_us_inequality(self):
        assert US_MODULE_DISPATCH["inequality"] is cm.compute_inequality_module_us

    def test_uk_budget_summary(self):
        assert (
            UK_MODULE_DISPATCH["budget_summary"] is cm.compute_budget_summary_module_uk
        )

    def test_us_budget_summary(self):
        assert (
            US_MODULE_DISPATCH["budget_summary"] is cm.compute_budget_summary_module_us
        )

    def test_constituency_is_uk_only(self):
        assert UK_MODULE_DISPATCH["constituency"] is cm.compute_constituency_module
        assert "constituency" not in US_MODULE_DISPATCH

    def test_local_authority_is_uk_only(self):
        assert (
            UK_MODULE_DISPATCH["local_authority"] is cm.compute_local_authority_module
        )
        assert "local_authority" not in US_MODULE_DISPATCH

    def test_wealth_decile_is_uk_only(self):
        assert UK_MODULE_DISPATCH["wealth_decile"] is cm.compute_wealth_decile_module
        assert "wealth_decile" not in US_MODULE_DISPATCH

    def test_congressional_district_is_us_only(self):
        assert (
            US_MODULE_DISPATCH["congressional_district"]
            is cm.compute_congressional_district_module
        )
        assert "congressional_district" not in UK_MODULE_DISPATCH


class TestModuleFunctionSignatures:
    """Tests that all module functions share the expected signature pattern.

    Modules use a common 7-param signature pattern:
        (pe_baseline_sim, pe_reform_sim, baseline_sim_id, reform_sim_id,
         report_id, session, **kwargs) -> None

    run_modules() passes country_id as a kwarg. Modules that need it (e.g.
    compute_decile_module) accept it explicitly; others accept **_kwargs.
    """

    _BASE_PARAMS = [
        "pe_baseline_sim",
        "pe_reform_sim",
        "baseline_sim_id",
        "reform_sim_id",
        "report_id",
        "session",
    ]
    # 7th param can be either explicit country_id or **_kwargs
    _VALID_7TH_PARAMS = {"country_id", "_kwargs"}

    def _get_all_unique_functions(self):
        """Collect all unique module functions from both dispatch tables."""
        seen = set()
        fns = []
        for fn in list(UK_MODULE_DISPATCH.values()) + list(US_MODULE_DISPATCH.values()):
            if id(fn) not in seen:
                seen.add(id(fn))
                fns.append(fn)
        return fns

    def test_all_functions_have_7_parameters(self):
        for fn in self._get_all_unique_functions():
            sig = inspect.signature(fn)
            assert len(sig.parameters) == 7, (
                f"{fn.__name__} has {len(sig.parameters)} params, expected 7"
            )

    def test_all_functions_have_expected_param_names(self):
        for fn in self._get_all_unique_functions():
            sig = inspect.signature(fn)
            param_names = list(sig.parameters.keys())
            # First 6 params must match exactly
            assert param_names[:6] == self._BASE_PARAMS, (
                f"{fn.__name__} first 6 params {param_names[:6]} != {self._BASE_PARAMS}"
            )
            # 7th param can be country_id or _kwargs
            assert param_names[6] in self._VALID_7TH_PARAMS, (
                f"{fn.__name__} 7th param '{param_names[6]}' not in {self._VALID_7TH_PARAMS}"
            )

    def test_all_functions_return_none(self):
        for fn in self._get_all_unique_functions():
            sig = inspect.signature(fn)
            # `from __future__ import annotations` makes annotations strings
            assert sig.return_annotation in (None, "None", inspect.Parameter.empty), (
                f"{fn.__name__} return annotation is {sig.return_annotation!r}, expected None"
            )


class TestRunModules:
    """Tests for the run_modules dispatch helper."""

    def _make_mock_dispatch(self, names):
        """Create a dispatch dict with mock functions."""
        return {name: MagicMock(name=f"compute_{name}") for name in names}

    def test_runs_all_when_modules_is_none(self):
        dispatch = self._make_mock_dispatch(["a", "b", "c"])
        session = MagicMock()
        ids = [uuid4() for _ in range(3)]

        run_modules(dispatch, None, "bl", "rf", ids[0], ids[1], ids[2], session)

        for fn in dispatch.values():
            fn.assert_called_once_with(
                "bl", "rf", ids[0], ids[1], ids[2], session, country_id=""
            )

    def test_runs_only_requested_modules(self):
        dispatch = self._make_mock_dispatch(["a", "b", "c"])
        session = MagicMock()
        ids = [uuid4() for _ in range(3)]

        run_modules(dispatch, ["b"], "bl", "rf", ids[0], ids[1], ids[2], session)

        dispatch["a"].assert_not_called()
        dispatch["b"].assert_called_once()
        dispatch["c"].assert_not_called()

    def test_ignores_unknown_module_names(self):
        dispatch = self._make_mock_dispatch(["a"])
        session = MagicMock()
        ids = [uuid4() for _ in range(3)]

        # Should not raise
        run_modules(
            dispatch, ["a", "nonexistent"], "bl", "rf", ids[0], ids[1], ids[2], session
        )

        dispatch["a"].assert_called_once()

    def test_empty_modules_list_runs_nothing(self):
        dispatch = self._make_mock_dispatch(["a", "b"])
        session = MagicMock()
        ids = [uuid4() for _ in range(3)]

        run_modules(dispatch, [], "bl", "rf", ids[0], ids[1], ids[2], session)

        for fn in dispatch.values():
            fn.assert_not_called()

    def test_preserves_call_order(self):
        """Modules should be called in the order they appear in the modules list."""
        call_order = []

        def make_tracker(name):
            def fn(*args, **kwargs):
                call_order.append(name)

            return fn

        dispatch = {name: make_tracker(name) for name in ["a", "b", "c"]}
        ids = [uuid4() for _ in range(3)]

        run_modules(
            dispatch, ["c", "a", "b"], "bl", "rf", ids[0], ids[1], ids[2], MagicMock()
        )

        assert call_order == ["c", "a", "b"]

    def test_none_modules_runs_all_in_dispatch_key_order(self):
        """When modules is None, all dispatch entries run in dict-iteration order."""
        call_order = []

        def make_tracker(name):
            def fn(*args, **kwargs):
                call_order.append(name)

            return fn

        dispatch = {name: make_tracker(name) for name in ["x", "y", "z"]}
        ids = [uuid4() for _ in range(3)]

        run_modules(dispatch, None, "bl", "rf", ids[0], ids[1], ids[2], MagicMock())

        assert call_order == ["x", "y", "z"]

    def test_passes_all_args_correctly(self):
        mock_fn = MagicMock()
        dispatch = {"test_mod": mock_fn}
        session = MagicMock()
        bl, rf, b_id, r_id, rep_id = "baseline", "reform", uuid4(), uuid4(), uuid4()

        run_modules(dispatch, ["test_mod"], bl, rf, b_id, r_id, rep_id, session)

        mock_fn.assert_called_once_with(
            bl, rf, b_id, r_id, rep_id, session, country_id=""
        )

    def test_duplicate_module_name_runs_twice(self):
        dispatch = self._make_mock_dispatch(["a"])
        session = MagicMock()
        ids = [uuid4() for _ in range(3)]

        run_modules(dispatch, ["a", "a"], "bl", "rf", ids[0], ids[1], ids[2], session)

        assert dispatch["a"].call_count == 2
