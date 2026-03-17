"""Composable computation module functions for economy analysis.

Each function computes a single module's results and writes DB records.
They share a common signature pattern:
    (pe_baseline_sim, pe_reform_sim, baseline_sim_id, reform_sim_id,
     report_id, session, config) -> None

run_modules() resolves the country's dispatch table and passes a
CountryConfig from the policyengine library to each module function.

Used by _run_local_economy_comparison_uk/us to run modules selectively.
"""

from __future__ import annotations

from uuid import UUID

from sqlmodel import Session

from policyengine_api.api.module_registry import MODULE_REGISTRY
from policyengine_api.models import (
    BudgetSummary,
    CongressionalDistrictImpact,
    ConstituencyImpact,
    DecileImpact,
    Inequality,
    IntraDecileImpact,
    LocalAuthorityImpact,
    Poverty,
    ProgramStatistics,
)

# ---------------------------------------------------------------------------
# Country configs — imported from the policyengine library
# ---------------------------------------------------------------------------

# Lazy-loaded to avoid importing heavy policyengine modules at import time.
# Callers should use get_country_config() instead.
_COUNTRY_CONFIGS: dict | None = None


def get_country_config(country_id: str):
    """Return the CountryConfig for the given country_id ('uk' or 'us')."""
    global _COUNTRY_CONFIGS
    if _COUNTRY_CONFIGS is None:
        from policyengine.outputs.country_config import UK_CONFIG, US_CONFIG

        _COUNTRY_CONFIGS = {"us": US_CONFIG, "uk": UK_CONFIG}
    config = _COUNTRY_CONFIGS.get(country_id)
    if config is None:
        raise ValueError(f"No CountryConfig for country '{country_id}'")
    return config


# ---------------------------------------------------------------------------
# Config-driven modules (shared UK + US)
# ---------------------------------------------------------------------------


def compute_decile_module(
    pe_baseline_sim,
    pe_reform_sim,
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    report_id: UUID,
    session: Session,
    config,
) -> None:
    """Compute income decile impacts (1-10) using config.income_variable."""
    from policyengine.outputs.decile_impact import compute_decile_impacts

    results = compute_decile_impacts(
        baseline_simulation=pe_baseline_sim,
        reform_simulation=pe_reform_sim,
        income_variable=config.income_variable,
    )
    for di in results.outputs:
        record = DecileImpact(
            baseline_simulation_id=baseline_sim_id,
            reform_simulation_id=reform_sim_id,
            report_id=report_id,
            income_variable=di.income_variable,
            entity=di.entity,
            decile=di.decile,
            quantiles=di.quantiles,
            baseline_mean=di.baseline_mean,
            reform_mean=di.reform_mean,
            absolute_change=di.absolute_change,
            relative_change=di.relative_change,
            count_better_off=di.count_better_off,
            count_worse_off=di.count_worse_off,
            count_no_change=di.count_no_change,
        )
        session.add(record)


def compute_intra_decile_module(
    pe_baseline_sim,
    pe_reform_sim,
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    report_id: UUID,
    session: Session,
    config,
) -> None:
    """Compute intra-decile income change distribution (5 bands)."""
    from policyengine.outputs.intra_decile_impact import (
        compute_intra_decile_impacts as pe_compute_intra_decile,
    )

    results = pe_compute_intra_decile(
        baseline_simulation=pe_baseline_sim,
        reform_simulation=pe_reform_sim,
        income_variable=config.income_variable,
    )
    for r in results.outputs:
        record = IntraDecileImpact(
            baseline_simulation_id=baseline_sim_id,
            reform_simulation_id=reform_sim_id,
            report_id=report_id,
            decile=r.decile,
            lose_more_than_5pct=r.lose_more_than_5pct,
            lose_less_than_5pct=r.lose_less_than_5pct,
            no_change=r.no_change,
            gain_less_than_5pct=r.gain_less_than_5pct,
            gain_more_than_5pct=r.gain_more_than_5pct,
        )
        session.add(record)


def compute_program_statistics_module(
    pe_baseline_sim,
    pe_reform_sim,
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    report_id: UUID,
    session: Session,
    config,
) -> None:
    """Compute program statistics using config.programs."""
    from policyengine.outputs.program_statistics import compute_program_statistics

    results = compute_program_statistics(
        baseline_simulation=pe_baseline_sim,
        reform_simulation=pe_reform_sim,
        programs=config.programs,
    )
    for ps in results.outputs:
        # Detect the name field (US: program_name, UK: programme_name)
        prog_name = getattr(ps, "program_name", None) or getattr(
            ps, "programme_name", None
        )
        record = ProgramStatistics(
            baseline_simulation_id=baseline_sim_id,
            reform_simulation_id=reform_sim_id,
            report_id=report_id,
            program_name=prog_name,
            entity=ps.entity,
            is_tax=ps.is_tax,
            baseline_total=ps.baseline_total,
            reform_total=ps.reform_total,
            change=ps.change,
            baseline_count=ps.baseline_count,
            reform_count=ps.reform_count,
            winners=ps.winners,
            losers=ps.losers,
        )
        session.add(record)


def compute_poverty_module(
    pe_baseline_sim,
    pe_reform_sim,
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    report_id: UUID,
    session: Session,
    config,
) -> None:
    """Compute poverty rates using config.country_id to select calculators."""
    if config.country_id == "uk":
        from policyengine.outputs.poverty import (
            calculate_uk_poverty_by_age,
            calculate_uk_poverty_by_gender,
            calculate_uk_poverty_rates,
        )

        calculators = [
            calculate_uk_poverty_rates,
            calculate_uk_poverty_by_age,
            calculate_uk_poverty_by_gender,
        ]
    else:
        from policyengine.outputs.poverty import (
            calculate_us_poverty_by_age,
            calculate_us_poverty_by_gender,
            calculate_us_poverty_by_race,
            calculate_us_poverty_rates,
        )

        calculators = [
            calculate_us_poverty_rates,
            calculate_us_poverty_by_age,
            calculate_us_poverty_by_gender,
            calculate_us_poverty_by_race,
        ]

    sim_pairs = [
        (pe_baseline_sim, baseline_sim_id),
        (pe_reform_sim, reform_sim_id),
    ]

    for calculator in calculators:
        for pe_sim, db_sim_id in sim_pairs:
            results = calculator(pe_sim)
            for pov in results.outputs:
                record = Poverty(
                    simulation_id=db_sim_id,
                    report_id=report_id,
                    poverty_type=pov.poverty_type,
                    entity=pov.entity,
                    filter_variable=pov.filter_variable,
                    headcount=pov.headcount,
                    total_population=pov.total_population,
                    rate=pov.rate,
                )
                session.add(record)


def compute_inequality_module(
    pe_baseline_sim,
    pe_reform_sim,
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    report_id: UUID,
    session: Session,
    config,
) -> None:
    """Compute inequality metrics using config.country_id to select calculator."""
    if config.country_id == "uk":
        from policyengine.outputs.inequality import calculate_uk_inequality as calc_fn
    else:
        from policyengine.outputs.inequality import calculate_us_inequality as calc_fn

    for pe_sim, db_sim_id in [
        (pe_baseline_sim, baseline_sim_id),
        (pe_reform_sim, reform_sim_id),
    ]:
        ineq = calc_fn(pe_sim)
        ineq.run()
        record = Inequality(
            simulation_id=db_sim_id,
            report_id=report_id,
            income_variable=ineq.income_variable,
            entity=ineq.entity,
            gini=ineq.gini,
            top_10_share=ineq.top_10_share,
            top_1_share=ineq.top_1_share,
            bottom_50_share=ineq.bottom_50_share,
        )
        session.add(record)


def compute_budget_summary_module(
    pe_baseline_sim,
    pe_reform_sim,
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    report_id: UUID,
    session: Session,
    config,
) -> None:
    """Compute budget summary using config.budget_variables."""
    from policyengine.outputs.budget_summary import compute_budget_summary

    results = compute_budget_summary(
        baseline_simulation=pe_baseline_sim,
        reform_simulation=pe_reform_sim,
        variables=config.budget_variables,
    )
    for item in results.outputs:
        record = BudgetSummary(
            baseline_simulation_id=baseline_sim_id,
            reform_simulation_id=reform_sim_id,
            report_id=report_id,
            variable_name=item.variable_name,
            entity=item.entity,
            baseline_total=item.baseline_total,
            reform_total=item.reform_total,
            change=item.change,
        )
        session.add(record)

    # Household count: raw sum of weights (bypasses Aggregate weighting)
    baseline_hh_count = float(
        pe_baseline_sim.output_dataset.data.household["household_weight"].values.sum()
    )
    reform_hh_count = float(
        pe_reform_sim.output_dataset.data.household["household_weight"].values.sum()
    )
    record = BudgetSummary(
        baseline_simulation_id=baseline_sim_id,
        reform_simulation_id=reform_sim_id,
        report_id=report_id,
        variable_name="household_count_total",
        entity="household",
        baseline_total=baseline_hh_count,
        reform_total=reform_hh_count,
        change=reform_hh_count - baseline_hh_count,
    )
    session.add(record)


# ---------------------------------------------------------------------------
# Geographic / country-specific modules (unchanged structure)
# ---------------------------------------------------------------------------


def compute_constituency_module(
    pe_baseline_sim,
    pe_reform_sim,
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    report_id: UUID,
    session: Session,
    config,
) -> None:
    """Compute UK parliamentary constituency impact."""
    from policyengine.outputs.constituency_impact import (
        compute_uk_constituency_impacts,
    )

    try:
        from policyengine_core.tools.google_cloud import download as gcs_download

        weight_matrix_path = gcs_download(
            gcs_bucket="policyengine-uk-data-private",
            gcs_key="parliamentary_constituency_weights.h5",
        )
        constituency_csv_path = gcs_download(
            gcs_bucket="policyengine-uk-data-private",
            gcs_key="constituencies_2024.csv",
        )
        impact = compute_uk_constituency_impacts(
            pe_baseline_sim,
            pe_reform_sim,
            weight_matrix_path=weight_matrix_path,
            constituency_csv_path=constituency_csv_path,
        )
        if impact.constituency_results:
            for cr in impact.constituency_results:
                record = ConstituencyImpact(
                    baseline_simulation_id=baseline_sim_id,
                    reform_simulation_id=reform_sim_id,
                    report_id=report_id,
                    constituency_code=cr["constituency_code"],
                    constituency_name=cr["constituency_name"],
                    x=cr["x"],
                    y=cr["y"],
                    average_household_income_change=cr[
                        "average_household_income_change"
                    ],
                    relative_household_income_change=cr[
                        "relative_household_income_change"
                    ],
                    population=cr["population"],
                )
                session.add(record)
    except FileNotFoundError:
        import logfire

        logfire.warning("Weight matrix not available, skipping constituency impact")


def compute_local_authority_module(
    pe_baseline_sim,
    pe_reform_sim,
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    report_id: UUID,
    session: Session,
    config,
) -> None:
    """Compute UK local authority impact."""
    from policyengine.outputs.local_authority_impact import (
        compute_uk_local_authority_impacts,
    )

    try:
        from policyengine_core.tools.google_cloud import download as gcs_download

        la_weight_matrix_path = gcs_download(
            gcs_bucket="policyengine-uk-data-private",
            gcs_key="local_authority_weights.h5",
        )
        la_csv_path = gcs_download(
            gcs_bucket="policyengine-uk-data-private",
            gcs_key="local_authorities_2021.csv",
        )
        impact = compute_uk_local_authority_impacts(
            pe_baseline_sim,
            pe_reform_sim,
            weight_matrix_path=la_weight_matrix_path,
            local_authority_csv_path=la_csv_path,
        )
        if impact.local_authority_results:
            for lr in impact.local_authority_results:
                record = LocalAuthorityImpact(
                    baseline_simulation_id=baseline_sim_id,
                    reform_simulation_id=reform_sim_id,
                    report_id=report_id,
                    local_authority_code=lr["local_authority_code"],
                    local_authority_name=lr["local_authority_name"],
                    x=lr["x"],
                    y=lr["y"],
                    average_household_income_change=lr[
                        "average_household_income_change"
                    ],
                    relative_household_income_change=lr[
                        "relative_household_income_change"
                    ],
                    population=lr["population"],
                )
                session.add(record)
    except FileNotFoundError:
        import logfire

        logfire.warning("Weight matrix not available, skipping local authority impact")


def compute_wealth_decile_module(
    pe_baseline_sim,
    pe_reform_sim,
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    report_id: UUID,
    session: Session,
    config,
) -> None:
    """Compute UK wealth decile impact and intra-wealth-decile breakdown."""
    from policyengine.core import Simulation as PESimulation
    from policyengine.outputs.decile_impact import DecileImpact as PEDecileImpact
    from policyengine.outputs.intra_decile_impact import (
        compute_intra_decile_impacts as pe_compute_intra_decile,
    )

    try:
        PEDecileImpact.model_rebuild(_types_namespace={"Simulation": PESimulation})
        for decile_num in range(1, 11):
            wealth_di = PEDecileImpact(
                baseline_simulation=pe_baseline_sim,
                reform_simulation=pe_reform_sim,
                income_variable="household_net_income",
                decile_variable="household_wealth_decile",
                entity="household",
                decile=decile_num,
            )
            wealth_di.run()
            record = DecileImpact(
                baseline_simulation_id=baseline_sim_id,
                reform_simulation_id=reform_sim_id,
                report_id=report_id,
                income_variable="household_wealth_decile",
                entity="household",
                decile=decile_num,
                quantiles=10,
                baseline_mean=wealth_di.baseline_mean,
                reform_mean=wealth_di.reform_mean,
                absolute_change=wealth_di.absolute_change,
                relative_change=wealth_di.relative_change,
            )
            session.add(record)

        # Intra-wealth-decile
        intra_wealth_results = pe_compute_intra_decile(
            baseline_simulation=pe_baseline_sim,
            reform_simulation=pe_reform_sim,
            income_variable="household_net_income",
            decile_variable="household_wealth_decile",
            entity="household",
        )
        for r in intra_wealth_results.outputs:
            record = IntraDecileImpact(
                baseline_simulation_id=baseline_sim_id,
                reform_simulation_id=reform_sim_id,
                report_id=report_id,
                decile_type="wealth",
                decile=r.decile,
                lose_more_than_5pct=r.lose_more_than_5pct,
                lose_less_than_5pct=r.lose_less_than_5pct,
                no_change=r.no_change,
                gain_less_than_5pct=r.gain_less_than_5pct,
                gain_more_than_5pct=r.gain_more_than_5pct,
            )
            session.add(record)
    except KeyError:
        import logfire

        logfire.warning(
            "household_wealth_decile not available, skipping wealth decile impact"
        )


def compute_congressional_district_module(
    pe_baseline_sim,
    pe_reform_sim,
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    report_id: UUID,
    session: Session,
    config,
) -> None:
    """Compute US congressional district impact."""
    from policyengine.outputs.congressional_district_impact import (
        compute_us_congressional_district_impacts,
    )

    try:
        impact = compute_us_congressional_district_impacts(
            pe_baseline_sim, pe_reform_sim
        )
    except KeyError:
        import logfire

        logfire.warning(
            "congressional_district_geoid not in dataset, skipping congressional district impact"
        )
        return
    if impact.district_results:
        for dr in impact.district_results:
            record = CongressionalDistrictImpact(
                baseline_simulation_id=baseline_sim_id,
                reform_simulation_id=reform_sim_id,
                report_id=report_id,
                district_geoid=dr["district_geoid"],
                state_fips=dr["state_fips"],
                district_number=dr["district_number"],
                average_household_income_change=dr["average_household_income_change"],
                relative_household_income_change=dr["relative_household_income_change"],
                population=dr["population"],
            )
            session.add(record)


# ---------------------------------------------------------------------------
# Single dispatch table: module name -> computation function
# ---------------------------------------------------------------------------

MODULE_DISPATCH: dict[str, type(compute_decile_module)] = {
    "decile": compute_decile_module,
    "intra_decile": compute_intra_decile_module,
    "program_statistics": compute_program_statistics_module,
    "poverty": compute_poverty_module,
    "inequality": compute_inequality_module,
    "budget_summary": compute_budget_summary_module,
    "constituency": compute_constituency_module,
    "local_authority": compute_local_authority_module,
    "wealth_decile": compute_wealth_decile_module,
    "congressional_district": compute_congressional_district_module,
}


def get_dispatch_for_country(country_id: str) -> dict:
    """Return the subset of MODULE_DISPATCH applicable to a country."""
    available = {m.name for m in MODULE_REGISTRY.values() if country_id in m.countries}
    return {k: v for k, v in MODULE_DISPATCH.items() if k in available}


def run_modules(
    country_id: str,
    modules: list[str] | None,
    pe_baseline_sim,
    pe_reform_sim,
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    report_id: UUID,
    session: Session,
) -> None:
    """Run the requested modules (or all applicable) for a country.

    Resolves the country's dispatch table and CountryConfig automatically.
    """
    dispatch = get_dispatch_for_country(country_id)
    config = get_country_config(country_id)
    to_run = modules if modules is not None else list(dispatch.keys())
    for mod_name in to_run:
        fn = dispatch.get(mod_name)
        if fn:
            fn(
                pe_baseline_sim,
                pe_reform_sim,
                baseline_sim_id,
                reform_sim_id,
                report_id,
                session,
                config,
            )
