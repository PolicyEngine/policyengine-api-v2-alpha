"""Fixtures and helpers for user-simulation association tests."""

from uuid import UUID

from policyengine_api.models import (
    Dataset,
    Simulation,
    SimulationStatus,
    TaxBenefitModel,
    TaxBenefitModelVersion,
    UserSimulationAssociation,
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


def create_simulation(session, model: TaxBenefitModel | None = None) -> Simulation:
    """Create and persist a Simulation with required dependencies."""
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

    simulation = Simulation(
        dataset_id=dataset.id,
        tax_benefit_model_version_id=version.id,
        status=SimulationStatus.COMPLETED,
    )
    session.add(simulation)
    session.commit()
    session.refresh(simulation)
    return simulation


def create_user_simulation_association(
    session,
    user_id: UUID,
    simulation: Simulation,
    country_id: str = "us",
    label: str | None = None,
) -> UserSimulationAssociation:
    """Create and persist a UserSimulationAssociation record."""
    record = UserSimulationAssociation(
        user_id=user_id,
        simulation_id=simulation.id,
        country_id=country_id,
        label=label,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record
