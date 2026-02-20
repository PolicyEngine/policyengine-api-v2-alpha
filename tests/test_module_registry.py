"""Tests for the economy analysis module registry."""

import pytest

from policyengine_api.api.module_registry import (
    MODULE_REGISTRY,
    ComputationModule,
    get_all_module_names,
    get_modules_for_country,
    validate_modules,
)


class TestModuleRegistry:
    """Tests for MODULE_REGISTRY contents."""

    def test_registry_is_not_empty(self):
        assert len(MODULE_REGISTRY) > 0

    def test_all_entries_are_computation_modules(self):
        for name, module in MODULE_REGISTRY.items():
            assert isinstance(module, ComputationModule)
            assert module.name == name

    def test_all_modules_have_countries(self):
        for module in MODULE_REGISTRY.values():
            assert len(module.countries) > 0
            for country in module.countries:
                assert country in ("uk", "us")

    def test_all_modules_have_response_fields(self):
        for module in MODULE_REGISTRY.values():
            assert len(module.response_fields) > 0

    def test_expected_modules_exist(self):
        expected = [
            "decile",
            "program_statistics",
            "poverty",
            "inequality",
            "budget_summary",
            "intra_decile",
            "congressional_district",
            "constituency",
            "local_authority",
            "wealth_decile",
        ]
        for name in expected:
            assert name in MODULE_REGISTRY, f"Missing module: {name}"


class TestCountryApplicability:
    """Tests for country-specific module availability."""

    def test_us_only_modules(self):
        assert "us" in MODULE_REGISTRY["congressional_district"].countries
        assert "uk" not in MODULE_REGISTRY["congressional_district"].countries

    def test_uk_only_modules(self):
        for name in ("constituency", "local_authority", "wealth_decile"):
            module = MODULE_REGISTRY[name]
            assert "uk" in module.countries
            assert "us" not in module.countries

    def test_shared_modules(self):
        shared = ["decile", "program_statistics", "poverty", "inequality",
                   "budget_summary", "intra_decile"]
        for name in shared:
            module = MODULE_REGISTRY[name]
            assert "uk" in module.countries
            assert "us" in module.countries


class TestGetModulesForCountry:
    """Tests for get_modules_for_country()."""

    def test_uk_includes_constituency(self):
        uk_modules = get_modules_for_country("uk")
        names = [m.name for m in uk_modules]
        assert "constituency" in names
        assert "local_authority" in names
        assert "wealth_decile" in names

    def test_uk_excludes_congressional_district(self):
        uk_modules = get_modules_for_country("uk")
        names = [m.name for m in uk_modules]
        assert "congressional_district" not in names

    def test_us_includes_congressional_district(self):
        us_modules = get_modules_for_country("us")
        names = [m.name for m in us_modules]
        assert "congressional_district" in names

    def test_us_excludes_uk_only(self):
        us_modules = get_modules_for_country("us")
        names = [m.name for m in us_modules]
        assert "constituency" not in names
        assert "local_authority" not in names
        assert "wealth_decile" not in names

    def test_unknown_country_returns_empty(self):
        assert get_modules_for_country("fr") == []


class TestGetAllModuleNames:
    """Tests for get_all_module_names()."""

    def test_returns_all_names(self):
        names = get_all_module_names()
        assert set(names) == set(MODULE_REGISTRY.keys())


class TestValidateModules:
    """Tests for validate_modules()."""

    def test_valid_us_modules(self):
        result = validate_modules(["decile", "poverty"], "us")
        assert result == ["decile", "poverty"]

    def test_valid_uk_modules(self):
        result = validate_modules(["constituency", "wealth_decile"], "uk")
        assert result == ["constituency", "wealth_decile"]

    def test_unknown_module_raises(self):
        with pytest.raises(ValueError, match="Unknown module"):
            validate_modules(["nonexistent"], "us")

    def test_wrong_country_raises(self):
        with pytest.raises(ValueError, match="not available for country"):
            validate_modules(["congressional_district"], "uk")

    def test_multiple_errors_combined(self):
        with pytest.raises(ValueError, match="Unknown module.*not available"):
            validate_modules(["nonexistent", "constituency"], "us")
