"""Tests for the composable computation module dispatch system."""

import inspect
from unittest.mock import MagicMock, patch
from uuid import uuid4

from policyengine_api.api import computation_modules as cm
from policyengine_api.api.computation_modules import (
    MODULE_DISPATCH,
    get_dispatch_for_country,
    run_modules,
)
from policyengine_api.api.module_registry import MODULE_REGISTRY


class TestModuleDispatch:
    """Tests for the unified MODULE_DISPATCH table."""

    def test_dispatch_keys_match_registry(self):
        """Every dispatch key should be a valid module in the registry."""
        for key in MODULE_DISPATCH:
            assert key in MODULE_REGISTRY, f"Dispatch key {key!r} not in registry"

    def test_dispatch_covers_all_registry_modules(self):
        """Dispatch should have an entry for every module in the registry."""
        assert set(MODULE_DISPATCH.keys()) == set(MODULE_REGISTRY.keys())

    def test_all_dispatch_values_are_callable(self):
        for fn in MODULE_DISPATCH.values():
            assert callable(fn)

    def test_dispatch_has_10_entries(self):
        assert len(MODULE_DISPATCH) == 10


class TestGetDispatchForCountry:
    """Tests for country-filtered dispatch tables."""

    def test_uk_dispatch_has_9_entries(self):
        uk = get_dispatch_for_country("uk")
        assert len(uk) == 9

    def test_us_dispatch_has_7_entries(self):
        us = get_dispatch_for_country("us")
        assert len(us) == 7

    def test_uk_dispatch_keys_match_registry(self):
        uk = get_dispatch_for_country("uk")
        uk_module_names = {
            name for name, mod in MODULE_REGISTRY.items() if "uk" in mod.countries
        }
        assert set(uk.keys()) == uk_module_names

    def test_us_dispatch_keys_match_registry(self):
        us = get_dispatch_for_country("us")
        us_module_names = {
            name for name, mod in MODULE_REGISTRY.items() if "us" in mod.countries
        }
        assert set(us.keys()) == us_module_names

    def test_constituency_is_uk_only(self):
        assert "constituency" in get_dispatch_for_country("uk")
        assert "constituency" not in get_dispatch_for_country("us")

    def test_local_authority_is_uk_only(self):
        assert "local_authority" in get_dispatch_for_country("uk")
        assert "local_authority" not in get_dispatch_for_country("us")

    def test_wealth_decile_is_uk_only(self):
        assert "wealth_decile" in get_dispatch_for_country("uk")
        assert "wealth_decile" not in get_dispatch_for_country("us")

    def test_congressional_district_is_us_only(self):
        assert "congressional_district" in get_dispatch_for_country("us")
        assert "congressional_district" not in get_dispatch_for_country("uk")


class TestUnifiedModuleFunctions:
    """Tests that shared modules use the same function for both countries."""

    def test_decile_is_shared(self):
        uk = get_dispatch_for_country("uk")
        us = get_dispatch_for_country("us")
        assert uk["decile"] is us["decile"]
        assert uk["decile"] is cm.compute_decile_module

    def test_intra_decile_is_shared(self):
        uk = get_dispatch_for_country("uk")
        us = get_dispatch_for_country("us")
        assert uk["intra_decile"] is us["intra_decile"]
        assert uk["intra_decile"] is cm.compute_intra_decile_module

    def test_program_statistics_is_shared(self):
        """A single function handles both UK and US program statistics."""
        uk = get_dispatch_for_country("uk")
        us = get_dispatch_for_country("us")
        assert uk["program_statistics"] is us["program_statistics"]
        assert uk["program_statistics"] is cm.compute_program_statistics_module

    def test_poverty_is_shared(self):
        uk = get_dispatch_for_country("uk")
        us = get_dispatch_for_country("us")
        assert uk["poverty"] is us["poverty"]
        assert uk["poverty"] is cm.compute_poverty_module

    def test_inequality_is_shared(self):
        uk = get_dispatch_for_country("uk")
        us = get_dispatch_for_country("us")
        assert uk["inequality"] is us["inequality"]
        assert uk["inequality"] is cm.compute_inequality_module

    def test_budget_summary_is_shared(self):
        uk = get_dispatch_for_country("uk")
        us = get_dispatch_for_country("us")
        assert uk["budget_summary"] is us["budget_summary"]
        assert uk["budget_summary"] is cm.compute_budget_summary_module


class TestModuleFunctionSignatures:
    """Tests that all module functions share the expected 7-param signature.

    Modules use a common signature pattern:
        (pe_baseline_sim, pe_reform_sim, baseline_sim_id, reform_sim_id,
         report_id, session, config) -> None
    """

    _EXPECTED_PARAMS = [
        "pe_baseline_sim",
        "pe_reform_sim",
        "baseline_sim_id",
        "reform_sim_id",
        "report_id",
        "session",
        "config",
    ]

    def _get_all_unique_functions(self):
        """Collect all unique module functions from dispatch."""
        seen = set()
        fns = []
        for fn in MODULE_DISPATCH.values():
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
            assert param_names == self._EXPECTED_PARAMS, (
                f"{fn.__name__} params {param_names} != {self._EXPECTED_PARAMS}"
            )

    def test_all_functions_return_none(self):
        for fn in self._get_all_unique_functions():
            sig = inspect.signature(fn)
            assert sig.return_annotation in (None, "None", inspect.Parameter.empty), (
                f"{fn.__name__} return annotation is {sig.return_annotation!r}, expected None"
            )


class TestRunModules:
    """Tests for the run_modules dispatch helper."""

    def _make_mock_dispatch(self, names):
        """Create a dispatch dict with mock functions."""
        return {name: MagicMock(name=f"compute_{name}") for name in names}

    def _mock_config(self):
        """Create a mock CountryConfig."""
        config = MagicMock()
        config.country_id = "us"
        return config

    @patch.object(cm, "get_dispatch_for_country")
    @patch.object(cm, "get_country_config")
    def test_runs_all_when_modules_is_none(self, mock_get_config, mock_get_dispatch):
        dispatch = self._make_mock_dispatch(["a", "b", "c"])
        config = self._mock_config()
        mock_get_dispatch.return_value = dispatch
        mock_get_config.return_value = config
        session = MagicMock()
        ids = [uuid4() for _ in range(3)]

        run_modules("us", None, "bl", "rf", ids[0], ids[1], ids[2], session)

        for fn in dispatch.values():
            fn.assert_called_once_with(
                "bl", "rf", ids[0], ids[1], ids[2], session, config
            )

    @patch.object(cm, "get_dispatch_for_country")
    @patch.object(cm, "get_country_config")
    def test_runs_only_requested_modules(self, mock_get_config, mock_get_dispatch):
        dispatch = self._make_mock_dispatch(["a", "b", "c"])
        config = self._mock_config()
        mock_get_dispatch.return_value = dispatch
        mock_get_config.return_value = config
        session = MagicMock()
        ids = [uuid4() for _ in range(3)]

        run_modules("us", ["b"], "bl", "rf", ids[0], ids[1], ids[2], session)

        dispatch["a"].assert_not_called()
        dispatch["b"].assert_called_once()
        dispatch["c"].assert_not_called()

    @patch.object(cm, "get_dispatch_for_country")
    @patch.object(cm, "get_country_config")
    def test_ignores_unknown_module_names(self, mock_get_config, mock_get_dispatch):
        dispatch = self._make_mock_dispatch(["a"])
        config = self._mock_config()
        mock_get_dispatch.return_value = dispatch
        mock_get_config.return_value = config
        session = MagicMock()
        ids = [uuid4() for _ in range(3)]

        # Should not raise
        run_modules(
            "us", ["a", "nonexistent"], "bl", "rf", ids[0], ids[1], ids[2], session
        )

        dispatch["a"].assert_called_once()

    @patch.object(cm, "get_dispatch_for_country")
    @patch.object(cm, "get_country_config")
    def test_empty_modules_list_runs_nothing(self, mock_get_config, mock_get_dispatch):
        dispatch = self._make_mock_dispatch(["a", "b"])
        config = self._mock_config()
        mock_get_dispatch.return_value = dispatch
        mock_get_config.return_value = config
        session = MagicMock()
        ids = [uuid4() for _ in range(3)]

        run_modules("us", [], "bl", "rf", ids[0], ids[1], ids[2], session)

        for fn in dispatch.values():
            fn.assert_not_called()

    @patch.object(cm, "get_dispatch_for_country")
    @patch.object(cm, "get_country_config")
    def test_preserves_call_order(self, mock_get_config, mock_get_dispatch):
        """Modules should be called in the order they appear in the modules list."""
        call_order = []
        config = self._mock_config()
        mock_get_config.return_value = config

        def make_tracker(name):
            def fn(*args, **kwargs):
                call_order.append(name)

            return fn

        dispatch = {name: make_tracker(name) for name in ["a", "b", "c"]}
        mock_get_dispatch.return_value = dispatch
        ids = [uuid4() for _ in range(3)]

        run_modules(
            "us", ["c", "a", "b"], "bl", "rf", ids[0], ids[1], ids[2], MagicMock()
        )

        assert call_order == ["c", "a", "b"]

    @patch.object(cm, "get_dispatch_for_country")
    @patch.object(cm, "get_country_config")
    def test_none_modules_runs_all_in_dispatch_key_order(
        self, mock_get_config, mock_get_dispatch
    ):
        """When modules is None, all dispatch entries run in dict-iteration order."""
        call_order = []
        config = self._mock_config()
        mock_get_config.return_value = config

        def make_tracker(name):
            def fn(*args, **kwargs):
                call_order.append(name)

            return fn

        dispatch = {name: make_tracker(name) for name in ["x", "y", "z"]}
        mock_get_dispatch.return_value = dispatch
        ids = [uuid4() for _ in range(3)]

        run_modules("us", None, "bl", "rf", ids[0], ids[1], ids[2], MagicMock())

        assert call_order == ["x", "y", "z"]

    @patch.object(cm, "get_dispatch_for_country")
    @patch.object(cm, "get_country_config")
    def test_passes_config_to_module_functions(
        self, mock_get_config, mock_get_dispatch
    ):
        mock_fn = MagicMock()
        config = self._mock_config()
        mock_get_config.return_value = config
        dispatch = {"test_mod": mock_fn}
        mock_get_dispatch.return_value = dispatch
        session = MagicMock()
        bl, rf, b_id, r_id, rep_id = "baseline", "reform", uuid4(), uuid4(), uuid4()

        run_modules("us", ["test_mod"], bl, rf, b_id, r_id, rep_id, session)

        mock_fn.assert_called_once_with(bl, rf, b_id, r_id, rep_id, session, config)

    @patch.object(cm, "get_dispatch_for_country")
    @patch.object(cm, "get_country_config")
    def test_duplicate_module_name_runs_twice(self, mock_get_config, mock_get_dispatch):
        dispatch = self._make_mock_dispatch(["a"])
        config = self._mock_config()
        mock_get_dispatch.return_value = dispatch
        mock_get_config.return_value = config
        session = MagicMock()
        ids = [uuid4() for _ in range(3)]

        run_modules("us", ["a", "a"], "bl", "rf", ids[0], ids[1], ids[2], session)

        assert dispatch["a"].call_count == 2
