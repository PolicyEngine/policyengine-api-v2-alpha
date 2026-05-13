from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import seed_regions  # noqa: E402


def test_region_filter_helpers_support_scoping_strategy_schema() -> None:
    region = SimpleNamespace(
        scoping_strategy=SimpleNamespace(
            strategy_type="row_filter",
            variable_name="place_fips",
            variable_value="03000",
        )
    )

    assert seed_regions._region_requires_filter(region) is True
    assert seed_regions._region_filter_field(region) == "place_fips"
    assert seed_regions._region_filter_value(region) == "03000"
    assert seed_regions._region_filter_strategy(region) == "row_filter"


def test_region_filter_helpers_support_legacy_filter_fields() -> None:
    region = SimpleNamespace(
        requires_filter=True,
        filter_field="country",
        filter_value="ENGLAND",
        scoping_strategy=None,
    )

    assert seed_regions._region_requires_filter(region) is True
    assert seed_regions._region_filter_field(region) == "country"
    assert seed_regions._region_filter_value(region) == "ENGLAND"
    assert seed_regions._region_filter_strategy(region) is None


def test_current_policyengine_regions_do_not_require_legacy_filter_attrs() -> None:
    from policyengine.countries.us.regions import us_region_registry

    place = next(
        region for region in us_region_registry.regions if region.region_type == "place"
    )

    assert not hasattr(place, "filter_field")
    assert seed_regions._region_requires_filter(place) is True
    assert seed_regions._region_filter_field(place) == "place_fips"
    assert seed_regions._region_filter_value(place)
    assert seed_regions._region_filter_strategy(place) == "row_filter"
