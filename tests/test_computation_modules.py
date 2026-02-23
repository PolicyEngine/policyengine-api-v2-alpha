"""Tests for the composable computation module dispatch system."""

from unittest.mock import MagicMock, patch

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
            name
            for name, mod in MODULE_REGISTRY.items()
            if "uk" in mod.countries
        }
        assert set(UK_MODULE_DISPATCH.keys()) == uk_module_names

    def test_us_dispatch_covers_us_modules(self):
        """US dispatch should have an entry for every US-applicable module."""
        us_module_names = {
            name
            for name, mod in MODULE_REGISTRY.items()
            if "us" in mod.countries
        }
        assert set(US_MODULE_DISPATCH.keys()) == us_module_names

    def test_all_dispatch_values_are_callable(self):
        for fn in UK_MODULE_DISPATCH.values():
            assert callable(fn)
        for fn in US_MODULE_DISPATCH.values():
            assert callable(fn)


class TestRunModules:
    """Tests for the run_modules dispatch helper."""

    def _make_mock_dispatch(self, names):
        """Create a dispatch dict with mock functions."""
        return {name: MagicMock(name=f"compute_{name}") for name in names}

    def test_runs_all_when_modules_is_none(self):
        dispatch = self._make_mock_dispatch(["a", "b", "c"])
        session = MagicMock()
        from uuid import uuid4

        ids = [uuid4() for _ in range(3)]

        run_modules(dispatch, None, "bl", "rf", ids[0], ids[1], ids[2], session)

        for fn in dispatch.values():
            fn.assert_called_once_with("bl", "rf", ids[0], ids[1], ids[2], session)

    def test_runs_only_requested_modules(self):
        dispatch = self._make_mock_dispatch(["a", "b", "c"])
        session = MagicMock()
        from uuid import uuid4

        ids = [uuid4() for _ in range(3)]

        run_modules(dispatch, ["b"], "bl", "rf", ids[0], ids[1], ids[2], session)

        dispatch["a"].assert_not_called()
        dispatch["b"].assert_called_once()
        dispatch["c"].assert_not_called()

    def test_ignores_unknown_module_names(self):
        dispatch = self._make_mock_dispatch(["a"])
        session = MagicMock()
        from uuid import uuid4

        ids = [uuid4() for _ in range(3)]

        # Should not raise
        run_modules(
            dispatch, ["a", "nonexistent"], "bl", "rf", ids[0], ids[1], ids[2], session
        )

        dispatch["a"].assert_called_once()

    def test_empty_modules_list_runs_nothing(self):
        dispatch = self._make_mock_dispatch(["a", "b"])
        session = MagicMock()
        from uuid import uuid4

        ids = [uuid4() for _ in range(3)]

        run_modules(dispatch, [], "bl", "rf", ids[0], ids[1], ids[2], session)

        for fn in dispatch.values():
            fn.assert_not_called()
