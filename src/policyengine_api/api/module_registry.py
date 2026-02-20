"""Economy analysis module registry.

Defines the available computation modules for economy-wide analysis.
Each module maps to a named computation (e.g., "poverty", "decile") with
metadata about which countries support it and which response fields it
populates.

Used by:
- GET /analysis/options — lists available modules
- POST /analysis/economy-custom — runs selected modules
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ComputationModule:
    """A named economy analysis computation module."""

    name: str
    label: str
    description: str
    countries: list[str] = field(default_factory=list)
    response_fields: list[str] = field(default_factory=list)


MODULE_REGISTRY: dict[str, ComputationModule] = {
    "decile": ComputationModule(
        name="decile",
        label="Income decile impacts",
        description="Relative and average income change by income decile (1-10).",
        countries=["uk", "us"],
        response_fields=["decile_impacts"],
    ),
    "program_statistics": ComputationModule(
        name="program_statistics",
        label="Program statistics",
        description="Per-program baseline/reform totals, changes, and winner/loser counts.",
        countries=["uk", "us"],
        response_fields=["program_statistics", "detailed_budget"],
    ),
    "poverty": ComputationModule(
        name="poverty",
        label="Poverty rates",
        description="Poverty rates by type, overall and by demographic breakdowns (age, gender, race).",
        countries=["uk", "us"],
        response_fields=["poverty"],
    ),
    "inequality": ComputationModule(
        name="inequality",
        label="Inequality metrics",
        description="Gini coefficient, top 10%/1% share, bottom 50% share.",
        countries=["uk", "us"],
        response_fields=["inequality"],
    ),
    "budget_summary": ComputationModule(
        name="budget_summary",
        label="Budget summary",
        description="Aggregate tax revenue, benefit spending, net income, and household count.",
        countries=["uk", "us"],
        response_fields=["budget_summary"],
    ),
    "intra_decile": ComputationModule(
        name="intra_decile",
        label="Intra-decile breakdown",
        description="Distribution of income change categories (5 bands) within each decile.",
        countries=["uk", "us"],
        response_fields=["intra_decile"],
    ),
    "congressional_district": ComputationModule(
        name="congressional_district",
        label="Congressional district impact",
        description="Per-district average and relative household income change for US congressional districts.",
        countries=["us"],
        response_fields=["congressional_district_impact"],
    ),
    "constituency": ComputationModule(
        name="constituency",
        label="Parliamentary constituency impact",
        description="Per-constituency average and relative household income change for UK parliamentary constituencies.",
        countries=["uk"],
        response_fields=["constituency_impact"],
    ),
    "local_authority": ComputationModule(
        name="local_authority",
        label="Local authority impact",
        description="Per-local-authority average and relative household income change for UK local authorities.",
        countries=["uk"],
        response_fields=["local_authority_impact"],
    ),
    "wealth_decile": ComputationModule(
        name="wealth_decile",
        label="Wealth decile impacts",
        description="Income change by wealth decile (1-10) and intra-wealth-decile breakdown.",
        countries=["uk"],
        response_fields=["wealth_decile", "intra_wealth_decile"],
    ),
}


def get_modules_for_country(country: str) -> list[ComputationModule]:
    """Return modules applicable to a country code ('uk' or 'us')."""
    return [m for m in MODULE_REGISTRY.values() if country in m.countries]


def get_all_module_names() -> list[str]:
    """Return all registered module names."""
    return list(MODULE_REGISTRY.keys())


def validate_modules(names: list[str], country: str) -> list[str]:
    """Validate module names against the registry for a given country.

    Returns the validated list. Raises ValueError for unknown or
    inapplicable modules.
    """
    available = {m.name for m in get_modules_for_country(country)}
    errors = []
    for name in names:
        if name not in MODULE_REGISTRY:
            errors.append(f"Unknown module: {name!r}")
        elif name not in available:
            errors.append(
                f"Module {name!r} is not available for country {country!r}"
            )
    if errors:
        raise ValueError("; ".join(errors))
    return names
