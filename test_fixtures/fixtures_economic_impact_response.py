"""Fixtures for economic impact response tests.

Provides factory functions to create completed reports with all output
table records (poverty, inequality, budget_summary, intra_decile,
program_statistics, decile_impacts) for testing _build_response().
"""

from uuid import uuid4

from sqlmodel import Session

from policyengine_api.models import (
    BudgetSummary,
    Dataset,
    DecileImpact,
    Inequality,
    IntraDecileImpact,
    Poverty,
    ProgramStatistics,
    Report,
    ReportStatus,
    Simulation,
    SimulationStatus,
    TaxBenefitModel,
    TaxBenefitModelVersion,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

UK_PROGRAMS = {
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

UK_PROGRAM_COUNT = len(UK_PROGRAMS)

BUDGET_VARIABLES_UK = [
    ("household_tax", "household"),
    ("household_benefits", "household"),
    ("household_net_income", "household"),
    ("household_count_total", "household"),
]

SAMPLE_POVERTY_TYPES = ["absolute_bhc", "absolute_ahc"]
SAMPLE_INEQUALITY_INCOME_VAR = "household_net_income"
SAMPLE_GINI = 0.35
SAMPLE_TOP_10_SHARE = 0.28
SAMPLE_TOP_1_SHARE = 0.10
SAMPLE_BOTTOM_50_SHARE = 0.22

INTRA_DECILE_DECILE_COUNT = 11  # 10 deciles + overall


# ---------------------------------------------------------------------------
# Core factory: report with simulations
# ---------------------------------------------------------------------------


def create_report_with_simulations(
    session: Session,
    status: ReportStatus = ReportStatus.COMPLETED,
) -> tuple[Report, Simulation, Simulation]:
    """Create a model, version, dataset, two simulations, and a report."""
    model = TaxBenefitModel(name="policyengine-uk", description="UK model")
    session.add(model)
    session.commit()
    session.refresh(model)

    version = TaxBenefitModelVersion(
        model_id=model.id, version="1.0.0", description="Test"
    )
    session.add(version)
    session.commit()
    session.refresh(version)

    dataset = Dataset(
        name="uk_test",
        description="Test dataset",
        filepath="test.h5",
        year=2024,
        tax_benefit_model_id=model.id,
    )
    session.add(dataset)
    session.commit()
    session.refresh(dataset)

    baseline_sim = Simulation(
        dataset_id=dataset.id,
        tax_benefit_model_version_id=version.id,
        status=SimulationStatus.COMPLETED,
    )
    reform_sim = Simulation(
        dataset_id=dataset.id,
        tax_benefit_model_version_id=version.id,
        status=SimulationStatus.COMPLETED,
    )
    session.add(baseline_sim)
    session.add(reform_sim)
    session.commit()
    session.refresh(baseline_sim)
    session.refresh(reform_sim)

    report = Report(
        label="Test economic impact report",
        baseline_simulation_id=baseline_sim.id,
        reform_simulation_id=reform_sim.id,
        status=status,
        report_type="economy_comparison",
    )
    session.add(report)
    session.commit()
    session.refresh(report)

    return report, baseline_sim, reform_sim


# ---------------------------------------------------------------------------
# Output record factories
# ---------------------------------------------------------------------------


def add_poverty_records(
    session: Session,
    report: Report,
    baseline_sim: Simulation,
    reform_sim: Simulation,
    count: int = 4,
) -> list[Poverty]:
    """Add poverty records to a report (for baseline and reform)."""
    records = []
    for sim in [baseline_sim, reform_sim]:
        for i, ptype in enumerate(SAMPLE_POVERTY_TYPES):
            rec = Poverty(
                simulation_id=sim.id,
                report_id=report.id,
                poverty_type=ptype,
                entity="person",
                filter_variable=None,
                headcount=float(1000 + i * 100),
                total_population=10000.0,
                rate=float(1000 + i * 100) / 10000.0,
            )
            session.add(rec)
            records.append(rec)
    session.commit()
    return records


def add_poverty_by_age_records(
    session: Session,
    report: Report,
    baseline_sim: Simulation,
    reform_sim: Simulation,
) -> list[Poverty]:
    """Add poverty-by-age records with filter_variable set."""
    records = []
    age_groups = [
        ("is_child", True),
        ("is_adult", True),
        ("is_SP_age", True),
    ]
    for sim in [baseline_sim, reform_sim]:
        for filter_var, _ in age_groups:
            for ptype in SAMPLE_POVERTY_TYPES:
                rec = Poverty(
                    simulation_id=sim.id,
                    report_id=report.id,
                    poverty_type=ptype,
                    entity="person",
                    filter_variable=filter_var,
                    headcount=500.0,
                    total_population=3000.0,
                    rate=500.0 / 3000.0,
                )
                session.add(rec)
                records.append(rec)
    session.commit()
    return records


def add_inequality_records(
    session: Session,
    report: Report,
    baseline_sim: Simulation,
    reform_sim: Simulation,
) -> list[Inequality]:
    """Add inequality records for baseline and reform."""
    records = []
    for sim in [baseline_sim, reform_sim]:
        rec = Inequality(
            simulation_id=sim.id,
            report_id=report.id,
            income_variable=SAMPLE_INEQUALITY_INCOME_VAR,
            entity="household",
            gini=SAMPLE_GINI,
            top_10_share=SAMPLE_TOP_10_SHARE,
            top_1_share=SAMPLE_TOP_1_SHARE,
            bottom_50_share=SAMPLE_BOTTOM_50_SHARE,
        )
        session.add(rec)
        records.append(rec)
    session.commit()
    return records


def add_budget_summary_records(
    session: Session,
    report: Report,
    baseline_sim: Simulation,
    reform_sim: Simulation,
) -> list[BudgetSummary]:
    """Add budget summary records for UK variables."""
    records = []
    for var_name, entity in BUDGET_VARIABLES_UK:
        rec = BudgetSummary(
            baseline_simulation_id=baseline_sim.id,
            reform_simulation_id=reform_sim.id,
            report_id=report.id,
            variable_name=var_name,
            entity=entity,
            baseline_total=1_000_000.0,
            reform_total=1_050_000.0,
            change=50_000.0,
        )
        session.add(rec)
        records.append(rec)
    session.commit()
    return records


def add_intra_decile_records(
    session: Session,
    report: Report,
    baseline_sim: Simulation,
    reform_sim: Simulation,
) -> list[IntraDecileImpact]:
    """Add 11 intra-decile impact records (deciles 1-10 + overall)."""
    records = []
    for decile_num in list(range(1, 11)) + [0]:
        rec = IntraDecileImpact(
            baseline_simulation_id=baseline_sim.id,
            reform_simulation_id=reform_sim.id,
            report_id=report.id,
            decile=decile_num,
            lose_more_than_5pct=0.0,
            lose_less_than_5pct=0.0,
            no_change=0.0,
            gain_less_than_5pct=1.0,
            gain_more_than_5pct=0.0,
        )
        session.add(rec)
        records.append(rec)
    session.commit()
    return records


def add_program_statistics_records(
    session: Session,
    report: Report,
    baseline_sim: Simulation,
    reform_sim: Simulation,
    programs: dict | None = None,
) -> list[ProgramStatistics]:
    """Add program statistics records. Defaults to full UK program list."""
    if programs is None:
        programs = UK_PROGRAMS
    records = []
    for prog_name, prog_info in programs.items():
        rec = ProgramStatistics(
            baseline_simulation_id=baseline_sim.id,
            reform_simulation_id=reform_sim.id,
            report_id=report.id,
            program_name=prog_name,
            entity=prog_info["entity"],
            is_tax=prog_info["is_tax"],
            baseline_total=500_000.0,
            reform_total=520_000.0,
            change=20_000.0,
            baseline_count=10_000.0,
            reform_count=10_000.0,
            winners=3_000.0,
            losers=2_000.0,
        )
        session.add(rec)
        records.append(rec)
    session.commit()
    return records


# ---------------------------------------------------------------------------
# Composite: fully populated report
# ---------------------------------------------------------------------------


def create_fully_populated_report(
    session: Session,
) -> tuple[Report, Simulation, Simulation]:
    """Create a completed report with records in ALL output tables."""
    report, baseline_sim, reform_sim = create_report_with_simulations(session)
    add_poverty_records(session, report, baseline_sim, reform_sim)
    add_poverty_by_age_records(session, report, baseline_sim, reform_sim)
    add_inequality_records(session, report, baseline_sim, reform_sim)
    add_budget_summary_records(session, report, baseline_sim, reform_sim)
    add_intra_decile_records(session, report, baseline_sim, reform_sim)
    add_program_statistics_records(session, report, baseline_sim, reform_sim)
    return report, baseline_sim, reform_sim
