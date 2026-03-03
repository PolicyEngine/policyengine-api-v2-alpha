"""Tests for economic impact analysis (analysis.py).

Unit tests for internal functions (_resolve_dataset_and_region,
_get_deterministic_simulation_id, _get_or_create_simulation) and
integration tests for the /analysis/economic-impact endpoint.
"""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from policyengine_api.api.analysis import (
    EconomicImpactRequest,
    _get_deterministic_simulation_id,
    _get_or_create_simulation,
    _resolve_dataset_and_region,
)
from policyengine_api.main import app
from policyengine_api.models import (
    Dataset,
    Simulation,
    SimulationStatus,
    SimulationType,
    TaxBenefitModel,
)
from test_fixtures.fixtures_regions import (
    create_dataset,
    create_region,
    create_tax_benefit_model,
    create_tax_benefit_model_version,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# _resolve_dataset_and_region
# ---------------------------------------------------------------------------


class TestResolveDatasetAndRegion:
    """Tests for _resolve_dataset_and_region."""

    # -- dataset_id path --

    def test__given_dataset_id__then_region_is_none(self, session: Session):
        model = create_tax_benefit_model(session, name="policyengine-uk")
        dataset = create_dataset(session, model, name="uk_enhanced_frs")
        request = EconomicImpactRequest(
            tax_benefit_model_name="policyengine_uk",
            dataset_id=dataset.id,
        )

        resolved_dataset, resolved_region = _resolve_dataset_and_region(
            request, session
        )

        assert resolved_region is None

    def test__given_dataset_id__then_dataset_is_returned(self, session: Session):
        model = create_tax_benefit_model(session, name="policyengine-uk")
        dataset = create_dataset(session, model, name="uk_enhanced_frs")
        request = EconomicImpactRequest(
            tax_benefit_model_name="policyengine_uk",
            dataset_id=dataset.id,
        )

        resolved_dataset, resolved_region = _resolve_dataset_and_region(
            request, session
        )

        assert resolved_dataset.id == dataset.id
        assert resolved_dataset.name == "uk_enhanced_frs"

    def test__given_dataset_id_and_region__then_region_takes_precedence(
        self, session: Session
    ):
        model = create_tax_benefit_model(session, name="policyengine-uk")
        dataset1 = create_dataset(session, model, name="dataset_from_id")
        dataset2 = create_dataset(session, model, name="dataset_from_region")
        create_region(
            session,
            model=model,
            dataset=dataset2,
            code="uk",
            label="United Kingdom",
            region_type="national",
            requires_filter=False,
        )
        request = EconomicImpactRequest(
            tax_benefit_model_name="policyengine_uk",
            dataset_id=dataset1.id,
            region="uk",
        )

        resolved_dataset, resolved_region = _resolve_dataset_and_region(
            request, session
        )

        assert resolved_dataset.id == dataset2.id
        assert resolved_region is not None
        assert resolved_region.code == "uk"

    # -- region with filter --

    def test__given_region_requires_filter__then_returns_filter_fields(
        self, session: Session
    ):
        model = create_tax_benefit_model(session, name="policyengine-uk")
        dataset = create_dataset(session, model, name="uk_enhanced_frs")
        create_region(
            session,
            model=model,
            dataset=dataset,
            code="country/england",
            label="England",
            region_type="country",
            requires_filter=True,
            filter_field="country",
            filter_value="ENGLAND",
        )
        request = EconomicImpactRequest(
            tax_benefit_model_name="policyengine_uk",
            region="country/england",
        )

        resolved_dataset, resolved_region = _resolve_dataset_and_region(
            request, session
        )

        assert resolved_region is not None
        assert resolved_region.filter_field == "country"
        assert resolved_region.filter_value == "ENGLAND"
        assert resolved_region.requires_filter is True

    def test__given_us_state_region__then_returns_state_filter(self, session: Session):
        model = create_tax_benefit_model(session, name="policyengine-us")
        dataset = create_dataset(session, model, name="us_cps")
        create_region(
            session,
            model=model,
            dataset=dataset,
            code="state/ca",
            label="California",
            region_type="state",
            requires_filter=True,
            filter_field="state_code",
            filter_value="CA",
        )
        request = EconomicImpactRequest(
            tax_benefit_model_name="policyengine_us",
            region="state/ca",
        )

        resolved_dataset, resolved_region = _resolve_dataset_and_region(
            request, session
        )

        assert resolved_region is not None
        assert resolved_region.filter_field == "state_code"
        assert resolved_region.filter_value == "CA"

    def test__given_region_with_filter__then_dataset_is_resolved(
        self, session: Session
    ):
        model = create_tax_benefit_model(session, name="policyengine-uk")
        dataset = create_dataset(session, model, name="uk_enhanced_frs")
        create_region(
            session,
            model=model,
            dataset=dataset,
            code="country/england",
            label="England",
            region_type="country",
            requires_filter=True,
            filter_field="country",
            filter_value="ENGLAND",
        )
        request = EconomicImpactRequest(
            tax_benefit_model_name="policyengine_uk",
            region="country/england",
        )

        resolved_dataset, resolved_region = _resolve_dataset_and_region(
            request, session
        )

        assert resolved_dataset.id == dataset.id
        assert resolved_dataset.name == "uk_enhanced_frs"

    # -- region without filter --

    def test__given_national_uk_region__then_filter_params_none(self, session: Session):
        model = create_tax_benefit_model(session, name="policyengine-uk")
        dataset = create_dataset(session, model, name="uk_enhanced_frs")
        create_region(
            session,
            model=model,
            dataset=dataset,
            code="uk",
            label="United Kingdom",
            region_type="national",
            requires_filter=False,
        )
        request = EconomicImpactRequest(
            tax_benefit_model_name="policyengine_uk",
            region="uk",
        )

        resolved_dataset, resolved_region = _resolve_dataset_and_region(
            request, session
        )

        assert resolved_region is not None
        assert resolved_region.requires_filter is False
        assert resolved_region.filter_field is None
        assert resolved_region.filter_value is None

    def test__given_national_us_region__then_filter_params_none(self, session: Session):
        model = create_tax_benefit_model(session, name="policyengine-us")
        dataset = create_dataset(session, model, name="us_cps")
        create_region(
            session,
            model=model,
            dataset=dataset,
            code="us",
            label="United States",
            region_type="national",
            requires_filter=False,
        )
        request = EconomicImpactRequest(
            tax_benefit_model_name="policyengine_us",
            region="us",
        )

        resolved_dataset, resolved_region = _resolve_dataset_and_region(
            request, session
        )

        assert resolved_region is not None
        assert resolved_region.requires_filter is False
        assert resolved_region.filter_field is None
        assert resolved_region.filter_value is None

    def test__given_national_region__then_dataset_still_resolved(
        self, session: Session
    ):
        model = create_tax_benefit_model(session, name="policyengine-uk")
        dataset = create_dataset(session, model, name="uk_enhanced_frs")
        create_region(
            session,
            model=model,
            dataset=dataset,
            code="uk",
            label="United Kingdom",
            region_type="national",
            requires_filter=False,
        )
        request = EconomicImpactRequest(
            tax_benefit_model_name="policyengine_uk",
            region="uk",
        )

        resolved_dataset, resolved_region = _resolve_dataset_and_region(
            request, session
        )

        assert resolved_dataset.id == dataset.id
        assert resolved_dataset.name == "uk_enhanced_frs"

    # -- error cases --

    def test__given_nonexistent_region_code__then_raises_404(self, session: Session):
        model = create_tax_benefit_model(session, name="policyengine-uk")
        create_dataset(session, model, name="uk_enhanced_frs")
        request = EconomicImpactRequest(
            tax_benefit_model_name="policyengine_uk",
            region="nonexistent/region",
        )

        with pytest.raises(HTTPException) as exc_info:
            _resolve_dataset_and_region(request, session)

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

    def test__given_region_for_wrong_model__then_raises_404(self, session: Session):
        uk_model = create_tax_benefit_model(session, name="policyengine-uk")
        uk_dataset = create_dataset(session, uk_model, name="uk_enhanced_frs")
        create_region(
            session,
            model=uk_model,
            dataset=uk_dataset,
            code="uk",
            label="United Kingdom",
            region_type="national",
        )
        request = EconomicImpactRequest(
            tax_benefit_model_name="policyengine_us",
            region="uk",
        )

        with pytest.raises(HTTPException) as exc_info:
            _resolve_dataset_and_region(request, session)

        assert exc_info.value.status_code == 404

    def test__given_neither_dataset_nor_region__then_raises_validation_error(
        self, session: Session
    ):
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="dataset_id or region"):
            EconomicImpactRequest(
                tax_benefit_model_name="policyengine_uk",
            )

    def test__given_nonexistent_dataset_id__then_raises_404(self, session: Session):
        nonexistent_id = uuid4()
        request = EconomicImpactRequest(
            tax_benefit_model_name="policyengine_uk",
            dataset_id=nonexistent_id,
        )

        with pytest.raises(HTTPException) as exc_info:
            _resolve_dataset_and_region(request, session)

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# _get_deterministic_simulation_id
# ---------------------------------------------------------------------------


class TestGetDeterministicSimulationId:
    """Tests for _get_deterministic_simulation_id."""

    def test__given_same_params__then_same_id_returned(self):
        dataset_id = uuid4()
        model_version_id = uuid4()
        policy_id = uuid4()
        dynamic_id = uuid4()

        id1 = _get_deterministic_simulation_id(
            SimulationType.ECONOMY,
            model_version_id,
            policy_id,
            dynamic_id,
            dataset_id=dataset_id,
            filter_field="country",
            filter_value="ENGLAND",
        )
        id2 = _get_deterministic_simulation_id(
            SimulationType.ECONOMY,
            model_version_id,
            policy_id,
            dynamic_id,
            dataset_id=dataset_id,
            filter_field="country",
            filter_value="ENGLAND",
        )

        assert id1 == id2

    def test__given_different_filter_field__then_different_id(self):
        dataset_id = uuid4()
        model_version_id = uuid4()

        id1 = _get_deterministic_simulation_id(
            SimulationType.ECONOMY,
            model_version_id,
            None,
            None,
            dataset_id=dataset_id,
            filter_field="country",
            filter_value="ENGLAND",
        )
        id2 = _get_deterministic_simulation_id(
            SimulationType.ECONOMY,
            model_version_id,
            None,
            None,
            dataset_id=dataset_id,
            filter_field="state_code",
            filter_value="ENGLAND",
        )

        assert id1 != id2

    def test__given_different_filter_value__then_different_id(self):
        dataset_id = uuid4()
        model_version_id = uuid4()

        id1 = _get_deterministic_simulation_id(
            SimulationType.ECONOMY,
            model_version_id,
            None,
            None,
            dataset_id=dataset_id,
            filter_field="country",
            filter_value="ENGLAND",
        )
        id2 = _get_deterministic_simulation_id(
            SimulationType.ECONOMY,
            model_version_id,
            None,
            None,
            dataset_id=dataset_id,
            filter_field="country",
            filter_value="SCOTLAND",
        )

        assert id1 != id2

    def test__given_filter_none_vs_filter_set__then_different_id(self):
        dataset_id = uuid4()
        model_version_id = uuid4()

        id_no_filter = _get_deterministic_simulation_id(
            SimulationType.ECONOMY,
            model_version_id,
            None,
            None,
            dataset_id=dataset_id,
            filter_field=None,
            filter_value=None,
        )
        id_with_filter = _get_deterministic_simulation_id(
            SimulationType.ECONOMY,
            model_version_id,
            None,
            None,
            dataset_id=dataset_id,
            filter_field="country",
            filter_value="ENGLAND",
        )

        assert id_no_filter != id_with_filter

    def test__given_different_dataset__then_different_id(self):
        model_version_id = uuid4()

        id1 = _get_deterministic_simulation_id(
            SimulationType.ECONOMY,
            model_version_id,
            None,
            None,
            dataset_id=uuid4(),
            filter_field="country",
            filter_value="ENGLAND",
        )
        id2 = _get_deterministic_simulation_id(
            SimulationType.ECONOMY,
            model_version_id,
            None,
            None,
            dataset_id=uuid4(),
            filter_field="country",
            filter_value="ENGLAND",
        )

        assert id1 != id2

    def test__given_null_optional_params__then_consistent_id(self):
        dataset_id = uuid4()
        model_version_id = uuid4()

        id1 = _get_deterministic_simulation_id(
            SimulationType.ECONOMY,
            model_version_id,
            None,
            None,
            dataset_id=dataset_id,
            filter_field=None,
            filter_value=None,
        )
        id2 = _get_deterministic_simulation_id(
            SimulationType.ECONOMY,
            model_version_id,
            None,
            None,
            dataset_id=dataset_id,
            filter_field=None,
            filter_value=None,
        )

        assert id1 == id2


# ---------------------------------------------------------------------------
# _get_or_create_simulation
# ---------------------------------------------------------------------------


class TestGetOrCreateSimulation:
    """Tests for _get_or_create_simulation."""

    def test__given_existing_simulation_with_filter__then_reuses(
        self, session: Session
    ):
        model = create_tax_benefit_model(session, name="policyengine-uk")
        model_version = create_tax_benefit_model_version(session, model)
        dataset = create_dataset(session, model, name="uk_enhanced_frs")

        first_sim = _get_or_create_simulation(
            simulation_type=SimulationType.ECONOMY,
            dataset_id=dataset.id,
            model_version_id=model_version.id,
            policy_id=None,
            dynamic_id=None,
            session=session,
            filter_field="country",
            filter_value="ENGLAND",
        )
        second_sim = _get_or_create_simulation(
            simulation_type=SimulationType.ECONOMY,
            dataset_id=dataset.id,
            model_version_id=model_version.id,
            policy_id=None,
            dynamic_id=None,
            session=session,
            filter_field="country",
            filter_value="ENGLAND",
        )

        assert first_sim.id == second_sim.id

    def test__given_different_filter__then_creates_new_simulation(
        self, session: Session
    ):
        model = create_tax_benefit_model(session, name="policyengine-uk")
        model_version = create_tax_benefit_model_version(session, model)
        dataset = create_dataset(session, model, name="uk_enhanced_frs")

        england_sim = _get_or_create_simulation(
            simulation_type=SimulationType.ECONOMY,
            dataset_id=dataset.id,
            model_version_id=model_version.id,
            policy_id=None,
            dynamic_id=None,
            session=session,
            filter_field="country",
            filter_value="ENGLAND",
        )
        scotland_sim = _get_or_create_simulation(
            simulation_type=SimulationType.ECONOMY,
            dataset_id=dataset.id,
            model_version_id=model_version.id,
            policy_id=None,
            dynamic_id=None,
            session=session,
            filter_field="country",
            filter_value="SCOTLAND",
        )

        assert england_sim.id != scotland_sim.id
        assert england_sim.filter_value == "ENGLAND"
        assert scotland_sim.filter_value == "SCOTLAND"

    def test__given_no_filter_vs_filter__then_creates_separate_simulations(
        self, session: Session
    ):
        model = create_tax_benefit_model(session, name="policyengine-uk")
        model_version = create_tax_benefit_model_version(session, model)
        dataset = create_dataset(session, model, name="uk_enhanced_frs")

        national_sim = _get_or_create_simulation(
            simulation_type=SimulationType.ECONOMY,
            dataset_id=dataset.id,
            model_version_id=model_version.id,
            policy_id=None,
            dynamic_id=None,
            session=session,
            filter_field=None,
            filter_value=None,
        )
        filtered_sim = _get_or_create_simulation(
            simulation_type=SimulationType.ECONOMY,
            dataset_id=dataset.id,
            model_version_id=model_version.id,
            policy_id=None,
            dynamic_id=None,
            session=session,
            filter_field="country",
            filter_value="ENGLAND",
        )

        assert national_sim.id != filtered_sim.id
        assert national_sim.filter_field is None
        assert filtered_sim.filter_field == "country"

    def test__given_new_simulation__then_status_is_pending(self, session: Session):
        model = create_tax_benefit_model(session, name="policyengine-uk")
        model_version = create_tax_benefit_model_version(session, model)
        dataset = create_dataset(session, model, name="uk_enhanced_frs")

        simulation = _get_or_create_simulation(
            simulation_type=SimulationType.ECONOMY,
            dataset_id=dataset.id,
            model_version_id=model_version.id,
            policy_id=None,
            dynamic_id=None,
            session=session,
            filter_field="country",
            filter_value="ENGLAND",
        )

        assert simulation.status == SimulationStatus.PENDING

    def test__given_filter_params__then_simulation_has_filter_fields(
        self, session: Session
    ):
        model = create_tax_benefit_model(session, name="policyengine-uk")
        model_version = create_tax_benefit_model_version(session, model)
        dataset = create_dataset(session, model, name="uk_enhanced_frs")

        simulation = _get_or_create_simulation(
            simulation_type=SimulationType.ECONOMY,
            dataset_id=dataset.id,
            model_version_id=model_version.id,
            policy_id=None,
            dynamic_id=None,
            session=session,
            filter_field="country",
            filter_value="ENGLAND",
        )

        assert simulation.filter_field == "country"
        assert simulation.filter_value == "ENGLAND"

    def test__given_no_filter_params__then_simulation_has_null_filter_fields(
        self, session: Session
    ):
        model = create_tax_benefit_model(session, name="policyengine-uk")
        model_version = create_tax_benefit_model_version(session, model)
        dataset = create_dataset(session, model, name="uk_enhanced_frs")

        simulation = _get_or_create_simulation(
            simulation_type=SimulationType.ECONOMY,
            dataset_id=dataset.id,
            model_version_id=model_version.id,
            policy_id=None,
            dynamic_id=None,
            session=session,
        )

        assert simulation.filter_field is None
        assert simulation.filter_value is None


# ---------------------------------------------------------------------------
# HTTP endpoint validation (no database required)
# ---------------------------------------------------------------------------


class TestEconomicImpactValidation:
    """Tests for request validation (no database required)."""

    def test_invalid_model_name(self):
        response = client.post(
            "/analysis/economic-impact",
            json={
                "tax_benefit_model_name": "invalid_model",
                "dataset_id": "00000000-0000-0000-0000-000000000000",
            },
        )
        assert response.status_code == 422

    def test_missing_dataset_id(self):
        response = client.post(
            "/analysis/economic-impact",
            json={
                "tax_benefit_model_name": "policyengine_uk",
            },
        )
        assert response.status_code == 422

    def test_invalid_uuid(self):
        response = client.post(
            "/analysis/economic-impact",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "dataset_id": "not-a-uuid",
            },
        )
        assert response.status_code == 422


@pytest.mark.integration
class TestEconomicImpactNotFound:
    """Tests for 404 responses."""

    def test_dataset_not_found(self):
        response = client.post(
            "/analysis/economic-impact",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "dataset_id": "00000000-0000-0000-0000-000000000000",
            },
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Integration tests (require running database with seeded data)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestEconomicImpactIntegration:
    """Integration tests for economic impact analysis.

    These tests require:
    1. A running Supabase instance
    2. Seeded database with UK/US models and datasets
    """

    @pytest.fixture
    def uk_dataset_id(self, session: Session):
        """Get a UK dataset ID from the database."""
        uk_model = session.exec(
            select(TaxBenefitModel).where(TaxBenefitModel.name == "uk")
        ).first()
        if not uk_model:
            pytest.skip("UK model not found in database")

        dataset = session.exec(
            select(Dataset).where(Dataset.tax_benefit_model_id == uk_model.id)
        ).first()
        if not dataset:
            pytest.skip("No UK dataset found in database")

        return dataset.id

    def test_uk_economic_impact_baseline_only(self, uk_dataset_id):
        response = client.post(
            "/analysis/economic-impact",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "dataset_id": str(uk_dataset_id),
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert "baseline_simulation_id" in data
        assert "reform_simulation_id" in data
        assert "decile_impacts" in data
        assert "programme_statistics" in data

        assert len(data["decile_impacts"]) == 10

        for di in data["decile_impacts"]:
            assert "decile" in di
            assert "baseline_mean" in di
            assert "reform_mean" in di
            assert "absolute_change" in di

    def test_simulations_created(self, uk_dataset_id, session: Session):
        response = client.post(
            "/analysis/economic-impact",
            json={
                "tax_benefit_model_name": "policyengine_uk",
                "dataset_id": str(uk_dataset_id),
            },
        )
        assert response.status_code == 200
        data = response.json()

        baseline_sim = session.get(Simulation, data["baseline_simulation_id"])
        assert baseline_sim is not None
        assert baseline_sim.status == "completed"

        reform_sim = session.get(Simulation, data["reform_simulation_id"])
        assert reform_sim is not None
        assert reform_sim.status == "completed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
