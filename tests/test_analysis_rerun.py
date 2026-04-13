from datetime import datetime, timezone

from policyengine_api.models import (
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

    triggered = {}

    def fake_trigger(report_id: str, country_id: str, db_session):
        triggered["report_id"] = report_id
        triggered["country_id"] = country_id

    monkeypatch.setattr(
        "policyengine_api.api.household_analysis._trigger_household_impact",
        fake_trigger,
    )

    response = client.post(f"/analysis/rerun/{report.id}")

    assert response.status_code == 200
    assert response.json() == {"report_id": str(report.id), "status": "pending"}
    assert triggered == {"report_id": str(report.id), "country_id": "uk"}

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
    )
    session.add(report)
    session.commit()
    session.refresh(report)

    triggered = {}

    def fake_trigger(report_id: str, country_id: str, db_session):
        triggered["report_id"] = report_id
        triggered["country_id"] = country_id

    monkeypatch.setattr(
        "policyengine_api.api.analysis._trigger_economy_comparison",
        fake_trigger,
    )

    response = client.post(f"/analysis/rerun/{report.id}")

    assert response.status_code == 200
    assert response.json() == {"report_id": str(report.id), "status": "pending"}
    assert triggered == {"report_id": str(report.id), "country_id": "us"}

    session.refresh(report)
    session.refresh(baseline_sim)
    session.refresh(reform_sim)

    assert report.status == ReportStatus.PENDING
    assert baseline_sim.status == SimulationStatus.PENDING
    assert reform_sim.status == SimulationStatus.PENDING
    assert baseline_sim.started_at is None
    assert reform_sim.started_at is None
    assert baseline_sim.completed_at is None
    assert reform_sim.completed_at is None
    assert baseline_sim.output_dataset_id is None
    assert reform_sim.output_dataset_id is None
