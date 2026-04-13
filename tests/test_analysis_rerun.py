from datetime import datetime, timezone

from sqlmodel import select

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
    Report,
    ReportStatus,
    ReportType,
    Simulation,
    SimulationStatus,
    SimulationType,
)
from test_fixtures.fixtures_household_analysis import (
    create_household_for_analysis,
    create_policy,
    setup_uk_model_and_version,
    setup_us_model_and_version,
)
from test_fixtures.fixtures_regions import create_dataset


def _count_rows_for_report(session, model, report_id):
    return len(session.exec(select(model).where(model.report_id == report_id)).all())


def _seed_economy_result_rows(session, report_id, baseline_sim_id, reform_sim_id):
    rows = [
        DecileImpact(
            baseline_simulation_id=baseline_sim_id,
            reform_simulation_id=reform_sim_id,
            report_id=report_id,
            income_variable="household_net_income",
            entity="household",
            decile=1,
            baseline_mean=100.0,
            reform_mean=110.0,
            absolute_change=10.0,
        ),
        ProgramStatistics(
            baseline_simulation_id=baseline_sim_id,
            reform_simulation_id=reform_sim_id,
            report_id=report_id,
            program_name="income_tax",
            entity="person",
            baseline_total=1000.0,
            reform_total=900.0,
            change=-100.0,
        ),
        Poverty(
            simulation_id=baseline_sim_id,
            report_id=report_id,
            poverty_type="spm",
            entity="person",
            headcount=100.0,
            total_population=1000.0,
            rate=0.1,
        ),
        Inequality(
            simulation_id=baseline_sim_id,
            report_id=report_id,
            income_variable="household_net_income",
            entity="household",
            gini=0.4,
        ),
        BudgetSummary(
            baseline_simulation_id=baseline_sim_id,
            reform_simulation_id=reform_sim_id,
            report_id=report_id,
            variable_name="household_tax",
            entity="household",
            baseline_total=1000.0,
            reform_total=900.0,
            change=-100.0,
        ),
        IntraDecileImpact(
            baseline_simulation_id=baseline_sim_id,
            reform_simulation_id=reform_sim_id,
            report_id=report_id,
            decile=1,
            lose_more_than_5pct=0.1,
            no_change=0.8,
            gain_more_than_5pct=0.1,
        ),
        CongressionalDistrictImpact(
            baseline_simulation_id=baseline_sim_id,
            reform_simulation_id=reform_sim_id,
            report_id=report_id,
            average_household_income_change=50.0,
            relative_household_income_change=0.01,
            population=1000.0,
            district_geoid=101,
            state_fips=6,
            district_number=12,
        ),
        ConstituencyImpact(
            baseline_simulation_id=baseline_sim_id,
            reform_simulation_id=reform_sim_id,
            report_id=report_id,
            average_household_income_change=25.0,
            relative_household_income_change=0.005,
            population=500.0,
            constituency_code="E14000001",
            constituency_name="Test Constituency",
            x=100,
            y=200,
        ),
        LocalAuthorityImpact(
            baseline_simulation_id=baseline_sim_id,
            reform_simulation_id=reform_sim_id,
            report_id=report_id,
            average_household_income_change=30.0,
            relative_household_income_change=0.006,
            population=750.0,
            local_authority_code="E06000001",
            local_authority_name="Test Authority",
            x=120,
            y=240,
        ),
    ]
    for row in rows:
        session.add(row)
    session.commit()

    return [
        DecileImpact,
        ProgramStatistics,
        Poverty,
        Inequality,
        BudgetSummary,
        IntraDecileImpact,
        CongressionalDistrictImpact,
        ConstituencyImpact,
        LocalAuthorityImpact,
    ]


def test_rerun_household_report_clears_household_results(client, session, monkeypatch):
    model, version = setup_uk_model_and_version(session)
    household = create_household_for_analysis(session, country_id="uk")
    reform_policy = create_policy(session, model.id, name="Household reform")
    started_at = datetime.now(timezone.utc)

    baseline_sim = Simulation(
        simulation_type=SimulationType.HOUSEHOLD,
        household_id=household.id,
        tax_benefit_model_version_id=version.id,
        status=SimulationStatus.COMPLETED,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
        household_result={"household": [{"net_income": 1000}]},
    )
    reform_sim = Simulation(
        simulation_type=SimulationType.HOUSEHOLD,
        household_id=household.id,
        policy_id=reform_policy.id,
        tax_benefit_model_version_id=version.id,
        status=SimulationStatus.COMPLETED,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
        household_result={"household": [{"net_income": 1200}]},
    )
    session.add(baseline_sim)
    session.add(reform_sim)
    session.commit()
    session.refresh(baseline_sim)
    session.refresh(reform_sim)

    report = Report(
        label="Household rerun",
        report_type=ReportType.HOUSEHOLD_COMPARISON,
        status=ReportStatus.COMPLETED,
        baseline_simulation_id=baseline_sim.id,
        reform_simulation_id=reform_sim.id,
        error_message="old error",
    )
    session.add(report)
    session.commit()
    session.refresh(report)

    household_triggered = {}
    economy_triggered = {}

    def fake_trigger(report_id: str, country_id: str, db_session):
        household_triggered["report_id"] = report_id
        household_triggered["country_id"] = country_id

    def fake_economy_trigger(report_id: str, country_id: str, db_session):
        economy_triggered["report_id"] = report_id
        economy_triggered["country_id"] = country_id

    monkeypatch.setattr(
        "policyengine_api.api.household_analysis._trigger_household_impact",
        fake_trigger,
    )
    monkeypatch.setattr(
        "policyengine_api.api.analysis._trigger_economy_comparison",
        fake_economy_trigger,
    )

    response = client.post(f"/analysis/rerun/{report.id}")

    assert response.status_code == 200
    assert response.json() == {"report_id": str(report.id), "status": "pending"}
    assert household_triggered == {"report_id": str(report.id), "country_id": "uk"}
    assert economy_triggered == {}

    session.refresh(report)
    session.refresh(baseline_sim)
    session.refresh(reform_sim)

    assert report.status == ReportStatus.PENDING
    assert report.error_message is None
    assert baseline_sim.status == SimulationStatus.PENDING
    assert reform_sim.status == SimulationStatus.PENDING
    assert baseline_sim.started_at is None
    assert reform_sim.started_at is None
    assert baseline_sim.completed_at is None
    assert reform_sim.completed_at is None
    assert baseline_sim.household_result is None
    assert reform_sim.household_result is None


def test_rerun_economy_report_clears_output_dataset_ids(client, session, monkeypatch):
    model, version = setup_us_model_and_version(session)
    input_dataset = create_dataset(session, model, name="us_input", filepath="us/input.h5")
    output_dataset = create_dataset(
        session, model, name="us_output", filepath="us/output.h5"
    )
    started_at = datetime.now(timezone.utc)

    baseline_sim = Simulation(
        simulation_type=SimulationType.ECONOMY,
        dataset_id=input_dataset.id,
        tax_benefit_model_version_id=version.id,
        status=SimulationStatus.COMPLETED,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
        output_dataset_id=output_dataset.id,
    )
    reform_sim = Simulation(
        simulation_type=SimulationType.ECONOMY,
        dataset_id=input_dataset.id,
        tax_benefit_model_version_id=version.id,
        status=SimulationStatus.COMPLETED,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
        output_dataset_id=output_dataset.id,
    )
    session.add(baseline_sim)
    session.add(reform_sim)
    session.commit()
    session.refresh(baseline_sim)
    session.refresh(reform_sim)

    report = Report(
        label="Economy rerun",
        report_type=ReportType.ECONOMY_COMPARISON,
        status=ReportStatus.COMPLETED,
        baseline_simulation_id=baseline_sim.id,
        reform_simulation_id=reform_sim.id,
        error_message="old error",
    )
    session.add(report)
    session.commit()
    session.refresh(report)

    result_models = _seed_economy_result_rows(
        session, report.id, baseline_sim.id, reform_sim.id
    )

    for model_class in result_models:
        assert _count_rows_for_report(session, model_class, report.id) == 1

    economy_triggered = {}
    household_triggered = {}

    def fake_trigger(report_id: str, country_id: str, db_session):
        economy_triggered["report_id"] = report_id
        economy_triggered["country_id"] = country_id

    def fake_household_trigger(report_id: str, country_id: str, db_session):
        household_triggered["report_id"] = report_id
        household_triggered["country_id"] = country_id

    monkeypatch.setattr(
        "policyengine_api.api.analysis._trigger_economy_comparison",
        fake_trigger,
    )
    monkeypatch.setattr(
        "policyengine_api.api.household_analysis._trigger_household_impact",
        fake_household_trigger,
    )

    response = client.post(f"/analysis/rerun/{report.id}")

    assert response.status_code == 200
    assert response.json() == {"report_id": str(report.id), "status": "pending"}
    assert economy_triggered == {"report_id": str(report.id), "country_id": "us"}
    assert household_triggered == {}

    session.refresh(report)
    session.refresh(baseline_sim)
    session.refresh(reform_sim)

    assert report.status == ReportStatus.PENDING
    assert report.error_message is None
    assert baseline_sim.status == SimulationStatus.PENDING
    assert reform_sim.status == SimulationStatus.PENDING
    assert baseline_sim.started_at is None
    assert reform_sim.started_at is None
    assert baseline_sim.completed_at is None
    assert reform_sim.completed_at is None
    assert baseline_sim.output_dataset_id is None
    assert reform_sim.output_dataset_id is None

    for model_class in result_models:
        assert _count_rows_for_report(session, model_class, report.id) == 0
