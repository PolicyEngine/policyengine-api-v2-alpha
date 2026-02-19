"""Fixtures and helpers for user-report association tests."""

from datetime import datetime
from uuid import UUID

from policyengine_api.models import (
    Dataset,
    Report,
    ReportStatus,
    Simulation,
    SimulationStatus,
    TaxBenefitModel,
    TaxBenefitModelVersion,
    UserReportAssociation,
)


def create_tax_benefit_model(
    session,
    name: str = "policyengine-us",
    description: str = "US model",
) -> TaxBenefitModel:
    """Create and persist a TaxBenefitModel record."""
    record = TaxBenefitModel(name=name, description=description)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def create_report(session, model: TaxBenefitModel | None = None) -> Report:
    """Create and persist a Report with required simulation dependencies."""
    if model is None:
        model = create_tax_benefit_model(session)

    version = TaxBenefitModelVersion(
        model_id=model.id, version="test", description="Test version"
    )
    session.add(version)
    session.commit()
    session.refresh(version)

    dataset = Dataset(
        name="test_dataset",
        description="Test dataset",
        filepath="test/path/dataset.h5",
        year=2024,
        tax_benefit_model_id=model.id,
    )
    session.add(dataset)
    session.commit()
    session.refresh(dataset)

    baseline = Simulation(
        dataset_id=dataset.id,
        tax_benefit_model_version_id=version.id,
        status=SimulationStatus.COMPLETED,
    )
    reform = Simulation(
        dataset_id=dataset.id,
        tax_benefit_model_version_id=version.id,
        status=SimulationStatus.COMPLETED,
    )
    session.add(baseline)
    session.add(reform)
    session.commit()
    session.refresh(baseline)
    session.refresh(reform)

    report = Report(
        label="Test report",
        status=ReportStatus.COMPLETED,
        baseline_simulation_id=baseline.id,
        reform_simulation_id=reform.id,
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return report


def create_user_report_association(
    session,
    user_id: UUID,
    report: Report,
    country_id: str = "us",
    label: str | None = None,
    last_run_at: datetime | None = None,
) -> UserReportAssociation:
    """Create and persist a UserReportAssociation record."""
    record = UserReportAssociation(
        user_id=user_id,
        report_id=report.id,
        country_id=country_id,
        label=label,
        last_run_at=last_run_at,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record
