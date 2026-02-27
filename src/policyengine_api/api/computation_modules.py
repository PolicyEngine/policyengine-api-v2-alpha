"""Composable computation module functions for economy analysis.

Each function computes a single module's results and writes DB records.
They share a common signature pattern:
    (pe_baseline_sim, pe_reform_sim, baseline_sim_id, reform_sim_id,
     report_id, session, **kwargs) -> None

run_modules() passes country_id as a kwarg. Modules that need it (e.g.
compute_decile_module) accept it explicitly; others accept **_kwargs.

Used by _run_local_economy_comparison_uk/us to run modules selectively.
"""

from __future__ import annotations

from uuid import UUID

from sqlmodel import Session

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
# Shared modules (UK + US)
# ---------------------------------------------------------------------------


DECILE_INCOME_VARIABLE: dict[str, str] = {
    "us": "household_net_income",
    "uk": "equiv_household_net_income",
}


def compute_decile_module(
    pe_baseline_sim,
    pe_reform_sim,
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    report_id: UUID,
    session: Session,
    country_id: str = "",
) -> None:
    """Compute income decile impacts (1-10)."""
    from policyengine.outputs import DecileImpact as PEDecileImpact

    if country_id not in DECILE_INCOME_VARIABLE:
        raise ValueError(f"No decile income variable configured for country '{country_id}'")

    income_variable = DECILE_INCOME_VARIABLE[country_id]

    for decile_num in range(1, 11):
        di = PEDecileImpact(
            baseline_simulation=pe_baseline_sim,
            reform_simulation=pe_reform_sim,
            decile=decile_num,
            income_variable=income_variable,
        )
        di.run()
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
    **_kwargs,
) -> None:
    """Compute intra-decile income change distribution (5 bands)."""
    from policyengine.outputs.intra_decile_impact import (
        compute_intra_decile_impacts as pe_compute_intra_decile,
    )

    results = pe_compute_intra_decile(
        baseline_simulation=pe_baseline_sim,
        reform_simulation=pe_reform_sim,
        income_variable="household_net_income",
        entity="household",
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


# ---------------------------------------------------------------------------
# UK-specific modules
# ---------------------------------------------------------------------------


def compute_program_statistics_module_uk(
    pe_baseline_sim,
    pe_reform_sim,
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    report_id: UUID,
    session: Session,
    **_kwargs,
) -> None:
    """Compute UK programme statistics."""
    from policyengine.core import Simulation as PESimulation
    from policyengine.tax_benefit_models.uk.outputs import (
        ProgrammeStatistics as PEProgrammeStats,
    )

    PEProgrammeStats.model_rebuild(_types_namespace={"Simulation": PESimulation})
    programmes = {
        "income_tax": {"entity": "person", "is_tax": True},
        "national_insurance": {"entity": "person", "is_tax": True},
        "vat": {"entity": "household", "is_tax": True},
        "council_tax": {"entity": "household", "is_tax": True},
        "universal_credit": {"entity": "person", "is_tax": False},
        "child_benefit": {"entity": "person", "is_tax": False},
        "pension_credit": {"entity": "person", "is_tax": False},
        "income_support": {"entity": "person", "is_tax": False},
        "working_tax_credit": {"entity": "person", "is_tax": False},
        "child_tax_credit": {"entity": "person", "is_tax": False},
    }
    for prog_name, prog_info in programmes.items():
        try:
            ps = PEProgrammeStats(
                baseline_simulation=pe_baseline_sim,
                reform_simulation=pe_reform_sim,
                programme_name=prog_name,
                entity=prog_info["entity"],
                is_tax=prog_info["is_tax"],
            )
            ps.run()
            record = ProgramStatistics(
                baseline_simulation_id=baseline_sim_id,
                reform_simulation_id=reform_sim_id,
                report_id=report_id,
                program_name=prog_name,
                entity=prog_info["entity"],
                is_tax=prog_info["is_tax"],
                baseline_total=ps.baseline_total,
                reform_total=ps.reform_total,
                change=ps.change,
                baseline_count=ps.baseline_count,
                reform_count=ps.reform_count,
                winners=ps.winners,
                losers=ps.losers,
            )
            session.add(record)
        except KeyError:
            pass


def compute_poverty_module_uk(
    pe_baseline_sim,
    pe_reform_sim,
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    report_id: UUID,
    session: Session,
    **_kwargs,
) -> None:
    """Compute UK poverty rates (overall, by age, by gender)."""
    from policyengine.outputs.poverty import (
        calculate_uk_poverty_by_age,
        calculate_uk_poverty_by_gender,
        calculate_uk_poverty_rates,
    )

    sim_pairs = [
        (pe_baseline_sim, baseline_sim_id),
        (pe_reform_sim, reform_sim_id),
    ]

    for calculator in [
        calculate_uk_poverty_rates,
        calculate_uk_poverty_by_age,
        calculate_uk_poverty_by_gender,
    ]:
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


def compute_inequality_module_uk(
    pe_baseline_sim,
    pe_reform_sim,
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    report_id: UUID,
    session: Session,
    **_kwargs,
) -> None:
    """Compute UK inequality metrics."""
    from policyengine.outputs.inequality import calculate_uk_inequality

    for pe_sim, db_sim_id in [
        (pe_baseline_sim, baseline_sim_id),
        (pe_reform_sim, reform_sim_id),
    ]:
        ineq = calculate_uk_inequality(pe_sim)
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


def compute_budget_summary_module_uk(
    pe_baseline_sim,
    pe_reform_sim,
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    report_id: UUID,
    session: Session,
    **_kwargs,
) -> None:
    """Compute UK budget summary aggregates."""
    from policyengine.core import Simulation as PESimulation
    from policyengine.outputs.aggregate import Aggregate as PEAggregate
    from policyengine.outputs.aggregate import AggregateType as PEAggregateType

    PEAggregate.model_rebuild(_types_namespace={"Simulation": PESimulation})

    uk_budget_variables = {
        "household_tax": "household",
        "household_benefits": "household",
        "household_net_income": "household",
    }
    for var_name, entity in uk_budget_variables.items():
        baseline_agg = PEAggregate(
            simulation=pe_baseline_sim,
            variable=var_name,
            aggregate_type=PEAggregateType.SUM,
            entity=entity,
        )
        baseline_agg.run()
        reform_agg = PEAggregate(
            simulation=pe_reform_sim,
            variable=var_name,
            aggregate_type=PEAggregateType.SUM,
            entity=entity,
        )
        reform_agg.run()
        record = BudgetSummary(
            baseline_simulation_id=baseline_sim_id,
            reform_simulation_id=reform_sim_id,
            report_id=report_id,
            variable_name=var_name,
            entity=entity,
            baseline_total=float(baseline_agg.result),
            reform_total=float(reform_agg.result),
            change=float(reform_agg.result - baseline_agg.result),
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


def compute_constituency_module(
    pe_baseline_sim,
    pe_reform_sim,
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    report_id: UUID,
    session: Session,
    **_kwargs,
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
    except Exception:
        pass  # Weight matrix not available


def compute_local_authority_module(
    pe_baseline_sim,
    pe_reform_sim,
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    report_id: UUID,
    session: Session,
    **_kwargs,
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
    except Exception:
        pass  # Weight matrix not available


def compute_wealth_decile_module(
    pe_baseline_sim,
    pe_reform_sim,
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    report_id: UUID,
    session: Session,
    **_kwargs,
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
    except (KeyError, Exception):
        pass  # household_wealth_decile not available


# ---------------------------------------------------------------------------
# US-specific modules
# ---------------------------------------------------------------------------


def compute_program_statistics_module_us(
    pe_baseline_sim,
    pe_reform_sim,
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    report_id: UUID,
    session: Session,
    **_kwargs,
) -> None:
    """Compute US program statistics."""
    from policyengine.core import Simulation as PESimulation
    from policyengine.tax_benefit_models.us.outputs import (
        ProgramStatistics as PEProgramStats,
    )

    PEProgramStats.model_rebuild(_types_namespace={"Simulation": PESimulation})
    programs = {
        "income_tax": {"entity": "tax_unit", "is_tax": True},
        "employee_payroll_tax": {"entity": "person", "is_tax": True},
        "snap": {"entity": "spm_unit", "is_tax": False},
        "tanf": {"entity": "spm_unit", "is_tax": False},
        "ssi": {"entity": "spm_unit", "is_tax": False},
        "social_security": {"entity": "person", "is_tax": False},
    }
    for prog_name, prog_info in programs.items():
        try:
            ps = PEProgramStats(
                baseline_simulation=pe_baseline_sim,
                reform_simulation=pe_reform_sim,
                program_name=prog_name,
                entity=prog_info["entity"],
                is_tax=prog_info["is_tax"],
            )
            ps.run()
            record = ProgramStatistics(
                baseline_simulation_id=baseline_sim_id,
                reform_simulation_id=reform_sim_id,
                report_id=report_id,
                program_name=prog_name,
                entity=prog_info["entity"],
                is_tax=prog_info["is_tax"],
                baseline_total=ps.baseline_total,
                reform_total=ps.reform_total,
                change=ps.change,
                baseline_count=ps.baseline_count,
                reform_count=ps.reform_count,
                winners=ps.winners,
                losers=ps.losers,
            )
            session.add(record)
        except KeyError:
            pass


def compute_poverty_module_us(
    pe_baseline_sim,
    pe_reform_sim,
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    report_id: UUID,
    session: Session,
    **_kwargs,
) -> None:
    """Compute US poverty rates (overall, by age, gender, race)."""
    from policyengine.outputs.poverty import (
        calculate_us_poverty_by_age,
        calculate_us_poverty_by_gender,
        calculate_us_poverty_by_race,
        calculate_us_poverty_rates,
    )

    sim_pairs = [
        (pe_baseline_sim, baseline_sim_id),
        (pe_reform_sim, reform_sim_id),
    ]

    for calculator in [
        calculate_us_poverty_rates,
        calculate_us_poverty_by_age,
        calculate_us_poverty_by_gender,
        calculate_us_poverty_by_race,
    ]:
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


def compute_inequality_module_us(
    pe_baseline_sim,
    pe_reform_sim,
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    report_id: UUID,
    session: Session,
    **_kwargs,
) -> None:
    """Compute US inequality metrics."""
    from policyengine.outputs.inequality import calculate_us_inequality

    for pe_sim, db_sim_id in [
        (pe_baseline_sim, baseline_sim_id),
        (pe_reform_sim, reform_sim_id),
    ]:
        ineq = calculate_us_inequality(pe_sim)
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


def compute_budget_summary_module_us(
    pe_baseline_sim,
    pe_reform_sim,
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    report_id: UUID,
    session: Session,
    **_kwargs,
) -> None:
    """Compute US budget summary aggregates."""
    from policyengine.core import Simulation as PESimulation
    from policyengine.outputs.aggregate import Aggregate as PEAggregate
    from policyengine.outputs.aggregate import AggregateType as PEAggregateType

    PEAggregate.model_rebuild(_types_namespace={"Simulation": PESimulation})

    us_budget_variables = {
        "household_tax": "household",
        "household_benefits": "household",
        "household_net_income": "household",
        "household_state_income_tax": "tax_unit",
    }
    for var_name, entity in us_budget_variables.items():
        baseline_agg = PEAggregate(
            simulation=pe_baseline_sim,
            variable=var_name,
            aggregate_type=PEAggregateType.SUM,
            entity=entity,
        )
        baseline_agg.run()
        reform_agg = PEAggregate(
            simulation=pe_reform_sim,
            variable=var_name,
            aggregate_type=PEAggregateType.SUM,
            entity=entity,
        )
        reform_agg.run()
        record = BudgetSummary(
            baseline_simulation_id=baseline_sim_id,
            reform_simulation_id=reform_sim_id,
            report_id=report_id,
            variable_name=var_name,
            entity=entity,
            baseline_total=float(baseline_agg.result),
            reform_total=float(reform_agg.result),
            change=float(reform_agg.result - baseline_agg.result),
        )
        session.add(record)

    # Household count: raw sum of weights
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


def compute_congressional_district_module(
    pe_baseline_sim,
    pe_reform_sim,
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    report_id: UUID,
    session: Session,
    **_kwargs,
) -> None:
    """Compute US congressional district impact."""
    from policyengine.outputs.congressional_district_impact import (
        compute_us_congressional_district_impacts,
    )

    try:
        impact = compute_us_congressional_district_impacts(
            pe_baseline_sim, pe_reform_sim
        )
        if impact.district_results:
            for dr in impact.district_results:
                record = CongressionalDistrictImpact(
                    baseline_simulation_id=baseline_sim_id,
                    reform_simulation_id=reform_sim_id,
                    report_id=report_id,
                    district_geoid=dr["district_geoid"],
                    state_fips=dr["state_fips"],
                    district_number=dr["district_number"],
                    average_household_income_change=dr[
                        "average_household_income_change"
                    ],
                    relative_household_income_change=dr[
                        "relative_household_income_change"
                    ],
                    population=dr["population"],
                )
                session.add(record)
    except KeyError:
        pass  # congressional_district_geoid not in dataset


# ---------------------------------------------------------------------------
# Dispatch tables: module name -> computation function
# ---------------------------------------------------------------------------

# Type alias for module computation functions
ModuleFunction = type(compute_decile_module)

UK_MODULE_DISPATCH: dict[str, ModuleFunction] = {
    "decile": compute_decile_module,
    "program_statistics": compute_program_statistics_module_uk,
    "poverty": compute_poverty_module_uk,
    "inequality": compute_inequality_module_uk,
    "budget_summary": compute_budget_summary_module_uk,
    "intra_decile": compute_intra_decile_module,
    "constituency": compute_constituency_module,
    "local_authority": compute_local_authority_module,
    "wealth_decile": compute_wealth_decile_module,
}

US_MODULE_DISPATCH: dict[str, ModuleFunction] = {
    "decile": compute_decile_module,
    "program_statistics": compute_program_statistics_module_us,
    "poverty": compute_poverty_module_us,
    "inequality": compute_inequality_module_us,
    "budget_summary": compute_budget_summary_module_us,
    "intra_decile": compute_intra_decile_module,
    "congressional_district": compute_congressional_district_module,
}


def run_modules(
    dispatch: dict[str, ModuleFunction],
    modules: list[str] | None,
    pe_baseline_sim,
    pe_reform_sim,
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    report_id: UUID,
    session: Session,
    country_id: str = "",
) -> None:
    """Run the requested modules (or all if modules is None)."""
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
                country_id=country_id,
            )
