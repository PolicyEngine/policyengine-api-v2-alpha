"""Fixtures and helpers for region-related tests."""

from uuid import uuid4

import pytest

from policyengine_api.models import (
    Dataset,
    Region,
    RegionDatasetLink,
    Simulation,
    SimulationStatus,
    TaxBenefitModel,
    TaxBenefitModelVersion,
)


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

TEST_UUIDS = {
    "DATASET": uuid4(),
    "DATASET_UK": uuid4(),
    "DATASET_US": uuid4(),
    "MODEL_UK": uuid4(),
    "MODEL_US": uuid4(),
    "MODEL_VERSION_UK": uuid4(),
    "MODEL_VERSION_US": uuid4(),
    "REGION_UK": uuid4(),
    "REGION_US_STATE": uuid4(),
    "REGION_US_NATIONAL": uuid4(),
    "POLICY": uuid4(),
    "DYNAMIC": uuid4(),
}

REGION_CODES = {
    "UK_ENGLAND": "country/england",
    "US_CALIFORNIA": "state/ca",
    "US_NATIONAL": "us",
    "UK_NATIONAL": "uk",
}

FILTER_FIELDS = {
    "UK_COUNTRY": "country",
    "US_STATE": "state_code",
    "US_FIPS": "place_fips",
}

FILTER_VALUES = {
    "ENGLAND": "ENGLAND",
    "CALIFORNIA": "CA",
    "CA_FIPS": "06000",
}


# -----------------------------------------------------------------------------
# Factory Functions
# -----------------------------------------------------------------------------


def create_tax_benefit_model(
    session, name: str = "policyengine-uk", description: str = "UK model"
) -> TaxBenefitModel:
    """Create and persist a TaxBenefitModel."""
    model = TaxBenefitModel(name=name, description=description)
    session.add(model)
    session.commit()
    session.refresh(model)
    return model


def create_tax_benefit_model_version(
    session, model: TaxBenefitModel, version: str = "1.0.0"
) -> TaxBenefitModelVersion:
    """Create and persist a TaxBenefitModelVersion."""
    model_version = TaxBenefitModelVersion(
        model_id=model.id,
        version=version,
        description=f"Version {version}",
    )
    session.add(model_version)
    session.commit()
    session.refresh(model_version)
    return model_version


def create_dataset(
    session,
    model: TaxBenefitModel,
    name: str = "test_dataset",
    filepath: str = "test/path/dataset.h5",
    year: int = 2024,
) -> Dataset:
    """Create and persist a Dataset."""
    dataset = Dataset(
        name=name,
        description=f"Test dataset: {name}",
        filepath=filepath,
        year=year,
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
    code: str,
    label: str,
    region_type: str,
    requires_filter: bool = False,
    filter_field: str | None = None,
    filter_value: str | None = None,
) -> Region:
    """Create and persist a Region with a dataset link."""
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


def create_simulation(
    session,
    dataset: Dataset,
    model_version: TaxBenefitModelVersion,
    filter_field: str | None = None,
    filter_value: str | None = None,
    status: SimulationStatus = SimulationStatus.PENDING,
) -> Simulation:
    """Create and persist a Simulation with optional filter parameters."""
    simulation = Simulation(
        dataset_id=dataset.id,
        tax_benefit_model_version_id=model_version.id,
        status=status,
        filter_field=filter_field,
        filter_value=filter_value,
    )
    session.add(simulation)
    session.commit()
    session.refresh(simulation)
    return simulation


# -----------------------------------------------------------------------------
# Composite Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def uk_model_and_version(session):
    """Create UK model with version."""
    model = create_tax_benefit_model(
        session, name="policyengine-uk", description="UK model"
    )
    version = create_tax_benefit_model_version(session, model)
    return model, version


@pytest.fixture
def us_model_and_version(session):
    """Create US model with version."""
    model = create_tax_benefit_model(
        session, name="policyengine-us", description="US model"
    )
    version = create_tax_benefit_model_version(session, model)
    return model, version


@pytest.fixture
def uk_dataset(session, uk_model_and_version):
    """Create a UK dataset."""
    model, _ = uk_model_and_version
    return create_dataset(
        session, model, name="uk_enhanced_frs", filepath="uk/enhanced_frs_2024.h5"
    )


@pytest.fixture
def us_dataset(session, us_model_and_version):
    """Create a US dataset."""
    model, _ = us_model_and_version
    return create_dataset(session, model, name="us_cps", filepath="us/cps_2024.h5")


@pytest.fixture
def uk_region_national(session, uk_model_and_version, uk_dataset):
    """Create UK national region (no filter required)."""
    model, _ = uk_model_and_version
    return create_region(
        session,
        model=model,
        dataset=uk_dataset,
        code="uk",
        label="United Kingdom",
        region_type="national",
        requires_filter=False,
    )


@pytest.fixture
def uk_region_england(session, uk_model_and_version, uk_dataset):
    """Create England region (filter required)."""
    model, _ = uk_model_and_version
    return create_region(
        session,
        model=model,
        dataset=uk_dataset,
        code="country/england",
        label="England",
        region_type="country",
        requires_filter=True,
        filter_field="country",
        filter_value="ENGLAND",
    )


@pytest.fixture
def us_region_national(session, us_model_and_version, us_dataset):
    """Create US national region (no filter required)."""
    model, _ = us_model_and_version
    return create_region(
        session,
        model=model,
        dataset=us_dataset,
        code="us",
        label="United States",
        region_type="national",
        requires_filter=False,
    )


@pytest.fixture
def us_region_california(session, us_model_and_version, us_dataset):
    """Create California state region (filter required)."""
    model, _ = us_model_and_version
    return create_region(
        session,
        model=model,
        dataset=us_dataset,
        code="state/ca",
        label="California",
        region_type="state",
        requires_filter=True,
        filter_field="state_code",
        filter_value="CA",
    )
