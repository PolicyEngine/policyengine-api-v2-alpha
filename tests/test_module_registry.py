"""Tests for the economy analysis module registry."""

from dataclasses import FrozenInstanceError

import pytest

from policyengine_api.api.analysis import EconomicImpactResponse
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

    def test_registry_has_exactly_10_modules(self):
        assert len(MODULE_REGISTRY) == 10

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

    def test_all_modules_have_non_empty_label(self):
        for name, module in MODULE_REGISTRY.items():
            assert module.label, f"Module {name!r} has empty label"
            assert len(module.label) > 0

    def test_all_modules_have_non_empty_description(self):
        for name, module in MODULE_REGISTRY.items():
            assert module.description, f"Module {name!r} has empty description"
            assert len(module.description) > 0

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

    def test_no_unexpected_modules(self):
        expected = {
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
        }
        assert set(MODULE_REGISTRY.keys()) == expected


class TestComputationModuleFrozen:
    """Tests that ComputationModule instances are immutable."""

    def test_cannot_mutate_name(self):
        module = MODULE_REGISTRY["decile"]
        with pytest.raises(FrozenInstanceError):
            module.name = "changed"

    def test_cannot_mutate_countries(self):
        module = MODULE_REGISTRY["decile"]
        with pytest.raises(FrozenInstanceError):
            module.countries = ["fr"]

    def test_cannot_mutate_response_fields(self):
        module = MODULE_REGISTRY["poverty"]
        with pytest.raises(FrozenInstanceError):
            module.response_fields = ["something_else"]


class TestResponseFieldsMapping:
    """Tests that each module's response_fields reference valid EconomicImpactResponse fields."""

    def test_all_response_fields_exist_on_response_model(self):
        valid_fields = set(EconomicImpactResponse.model_fields.keys())
        for name, module in MODULE_REGISTRY.items():
            for field in module.response_fields:
                assert field in valid_fields, (
                    f"Module {name!r} references response field {field!r} "
                    f"which does not exist on EconomicImpactResponse"
                )

    def test_decile_response_fields(self):
        assert MODULE_REGISTRY["decile"].response_fields == ["decile_impacts"]

    def test_program_statistics_includes_detailed_budget(self):
        fields = MODULE_REGISTRY["program_statistics"].response_fields
        assert "program_statistics" in fields
        assert "detailed_budget" in fields

    def test_poverty_response_fields(self):
        assert MODULE_REGISTRY["poverty"].response_fields == ["poverty"]

    def test_inequality_response_fields(self):
        assert MODULE_REGISTRY["inequality"].response_fields == ["inequality"]

    def test_budget_summary_response_fields(self):
        assert MODULE_REGISTRY["budget_summary"].response_fields == ["budget_summary"]

    def test_intra_decile_response_fields(self):
        assert MODULE_REGISTRY["intra_decile"].response_fields == ["intra_decile"]

    def test_congressional_district_response_fields(self):
        assert MODULE_REGISTRY["congressional_district"].response_fields == [
            "congressional_district_impact"
        ]

    def test_constituency_response_fields(self):
        assert MODULE_REGISTRY["constituency"].response_fields == [
            "constituency_impact"
        ]

    def test_local_authority_response_fields(self):
        assert MODULE_REGISTRY["local_authority"].response_fields == [
            "local_authority_impact"
        ]

    def test_wealth_decile_includes_both_fields(self):
        fields = MODULE_REGISTRY["wealth_decile"].response_fields
        assert "wealth_decile" in fields
        assert "intra_wealth_decile" in fields


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
        shared = [
            "decile",
            "program_statistics",
            "poverty",
            "inequality",
            "budget_summary",
            "intra_decile",
        ]
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

    def test_uk_has_9_modules(self):
        uk_modules = get_modules_for_country("uk")
        assert len(uk_modules) == 9

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

    def test_us_has_7_modules(self):
        us_modules = get_modules_for_country("us")
        assert len(us_modules) == 7

    def test_unknown_country_returns_empty(self):
        assert get_modules_for_country("fr") == []

    def test_returns_computation_module_instances(self):
        for m in get_modules_for_country("uk"):
            assert isinstance(m, ComputationModule)


class TestGetAllModuleNames:
    """Tests for get_all_module_names()."""

    def test_returns_all_names(self):
        names = get_all_module_names()
        assert set(names) == set(MODULE_REGISTRY.keys())

    def test_returns_list_of_strings(self):
        names = get_all_module_names()
        assert isinstance(names, list)
        for name in names:
            assert isinstance(name, str)


class TestValidateModules:
    """Tests for validate_modules()."""

    def test_valid_us_modules(self):
        result = validate_modules(["decile", "poverty"], "us")
        assert result == ["decile", "poverty"]

    def test_valid_uk_modules(self):
        result = validate_modules(["constituency", "wealth_decile"], "uk")
        assert result == ["constituency", "wealth_decile"]

    def test_empty_list_passes_validation(self):
        result = validate_modules([], "us")
        assert result == []

    def test_all_us_modules_pass_validation(self):
        us_names = [m.name for m in get_modules_for_country("us")]
        result = validate_modules(us_names, "us")
        assert result == us_names

    def test_all_uk_modules_pass_validation(self):
        uk_names = [m.name for m in get_modules_for_country("uk")]
        result = validate_modules(uk_names, "uk")
        assert result == uk_names

    def test_unknown_module_raises(self):
        with pytest.raises(ValueError, match="Unknown module"):
            validate_modules(["nonexistent"], "us")

    def test_wrong_country_raises(self):
        with pytest.raises(ValueError, match="not available for country"):
            validate_modules(["congressional_district"], "uk")

    def test_multiple_errors_combined(self):
        with pytest.raises(ValueError, match="Unknown module.*not available"):
            validate_modules(["nonexistent", "constituency"], "us")

    def test_returns_original_list_on_success(self):
        names = ["poverty", "decile", "inequality"]
        result = validate_modules(names, "us")
        assert result is names
