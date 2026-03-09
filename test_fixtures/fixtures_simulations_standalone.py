"""Fixtures and helpers for standalone simulation endpoint tests."""

from policyengine_api.models import (
    Dataset,
    Household,
    Policy,
    Region,
    RegionDatasetLink,
    Simulation,
    SimulationStatus,
    SimulationType,
    TaxBenefitModel,
    TaxBenefitModelVersion,
)


def create_us_model_and_version(
    session,
) -> tuple[TaxBenefitModel, TaxBenefitModelVersion]:
    """Create a US tax-benefit model and version."""
    model = TaxBenefitModel(name="policyengine-us", description="US model")
    session.add(model)
    session.commit()
    session.refresh(model)

    version = TaxBenefitModelVersion(
        model_id=model.id, version="test", description="Test version"
    )
    session.add(version)
    session.commit()
    session.refresh(version)

    return model, version


def create_uk_model_and_version(
    session,
) -> tuple[TaxBenefitModel, TaxBenefitModelVersion]:
    """Create a UK tax-benefit model and version."""
    model = TaxBenefitModel(name="policyengine-uk", description="UK model")
    session.add(model)
    session.commit()
    session.refresh(model)

    version = TaxBenefitModelVersion(
        model_id=model.id, version="test", description="Test version"
    )
    session.add(version)
    session.commit()
    session.refresh(version)

    return model, version


def create_household(
    session,
    tax_benefit_model_name: str = "policyengine_us",
    year: int = 2024,
    label: str = "Test household",
) -> Household:
    """Create and persist a Household record."""
    household = Household(
        tax_benefit_model_name=tax_benefit_model_name,
        year=year,
        label=label,
        household_data={
            "people": [{"age": {"2024": 30}, "employment_income": {"2024": 50000}}],
            "household": [{"state_code": {"2024": "CA"}}],
        },
    )
    session.add(household)
    session.commit()
    session.refresh(household)
    return household


def create_policy(session, model: TaxBenefitModel) -> Policy:
    """Create and persist a Policy record."""
    policy = Policy(
        name="Test reform",
        description="A test reform policy",
        tax_benefit_model_id=model.id,
    )
    session.add(policy)
    session.commit()
    session.refresh(policy)
    return policy


def create_dataset(session, model: TaxBenefitModel) -> Dataset:
    """Create and persist a Dataset record."""
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
    return dataset


def create_region(
    session,
    model: TaxBenefitModel,
    dataset: Dataset,
    code: str = "us",
    label: str = "United States",
    region_type: str = "country",
    requires_filter: bool = False,
    filter_field: str | None = None,
    filter_value: str | None = None,
) -> Region:
    """Create and persist a Region record with a dataset link."""
    region = Region(
        code=code,
        label=label,
        region_type=region_type,
        requires_filter=requires_filter,
        filter_field=filter_field,
        filter_value=filter_value,
        tax_benefit_model_id=model.id,
    )
    session.add(region)
    session.commit()
    session.refresh(region)

    # Create the join table link
    link = RegionDatasetLink(region_id=region.id, dataset_id=dataset.id)
    session.add(link)
    session.commit()

    return region


def create_economy_simulation(
    session,
    version: TaxBenefitModelVersion,
    dataset: Dataset,
) -> Simulation:
    """Create and persist an economy Simulation record."""
    simulation = Simulation(
        simulation_type=SimulationType.ECONOMY,
        dataset_id=dataset.id,
        tax_benefit_model_version_id=version.id,
        status=SimulationStatus.COMPLETED,
    )
    session.add(simulation)
    session.commit()
    session.refresh(simulation)
    return simulation


def create_household_simulation(
    session,
    version: TaxBenefitModelVersion,
    household: Household,
) -> Simulation:
    """Create and persist a household Simulation record."""
    simulation = Simulation(
        simulation_type=SimulationType.HOUSEHOLD,
        household_id=household.id,
        tax_benefit_model_version_id=version.id,
        status=SimulationStatus.COMPLETED,
        household_result={"person": [{"income_tax": {"2024": 5000}}]},
    )
    session.add(simulation)
    session.commit()
    session.refresh(simulation)
    return simulation
