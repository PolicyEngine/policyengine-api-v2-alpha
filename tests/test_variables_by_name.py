"""Tests for POST /variables/by-name endpoint."""

from datetime import datetime, timezone

import pytest

from policyengine_api.models import (
    TaxBenefitModel,
    TaxBenefitModelVersion,
    Variable,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def uk_version(session):
    """Create a policyengine-uk model and version."""
    model = TaxBenefitModel(name="policyengine-uk", description="UK model")
    session.add(model)
    session.commit()
    session.refresh(model)

    version = TaxBenefitModelVersion(
        model_id=model.id, version="1.0", description="UK v1"
    )
    session.add(version)
    session.commit()
    session.refresh(version)
    return version


@pytest.fixture
def us_version(session):
    """Create a policyengine-us model and version."""
    model = TaxBenefitModel(name="policyengine-us", description="US model")
    session.add(model)
    session.commit()
    session.refresh(model)

    version = TaxBenefitModelVersion(
        model_id=model.id, version="1.0", description="US v1"
    )
    session.add(version)
    session.commit()
    session.refresh(version)
    return version


def _add_var(session, version, name, entity="person", description=None):
    """Create and persist a Variable."""
    var = Variable(
        name=name,
        entity=entity,
        description=description,
        tax_benefit_model_version_id=version.id,
    )
    session.add(var)
    session.commit()
    session.refresh(var)
    return var


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVariablesByName:
    """Tests for looking up variables by their exact names."""

    def test_returns_matching_variables(self, client, session, uk_version):
        """Given known variable names, returns their full metadata."""
        _add_var(session, uk_version, "employment_income")
        _add_var(session, uk_version, "income_tax")

        response = client.post(
            "/variables/by-name",
            json={
                "names": ["employment_income", "income_tax"],
                "tax_benefit_model_name": "policyengine-uk",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        returned_names = {v["name"] for v in data}
        assert returned_names == {"employment_income", "income_tax"}

    def test_returns_empty_list_for_empty_names(self, client, session, uk_version):
        """Given an empty names list, returns an empty list."""
        response = client.post(
            "/variables/by-name",
            json={
                "names": [],
                "tax_benefit_model_name": "policyengine-uk",
            },
        )

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_empty_list_for_unknown_names(self, client, session, uk_version):
        """Given names that don't match any variable, returns an empty list."""
        _add_var(session, uk_version, "employment_income")

        response = client.post(
            "/variables/by-name",
            json={
                "names": ["nonexistent_var", "also_missing"],
                "tax_benefit_model_name": "policyengine-uk",
            },
        )

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_only_matching_when_mix_of_known_and_unknown(
        self, client, session, uk_version
    ):
        """Given a mix of known and unknown names, returns only the known ones."""
        _add_var(session, uk_version, "income_tax")

        response = client.post(
            "/variables/by-name",
            json={
                "names": ["income_tax", "fake_var"],
                "tax_benefit_model_name": "policyengine-uk",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "income_tax"

    def test_single_name_lookup(self, client, session, uk_version):
        """Looking up a single variable name works."""
        _add_var(session, uk_version, "age")

        response = client.post(
            "/variables/by-name",
            json={
                "names": ["age"],
                "tax_benefit_model_name": "policyengine-uk",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "age"

    def test_results_ordered_by_name(self, client, session, uk_version):
        """Returned variables are sorted alphabetically by name."""
        _add_var(session, uk_version, "zzz_var")
        _add_var(session, uk_version, "aaa_var")
        _add_var(session, uk_version, "mmm_var")

        response = client.post(
            "/variables/by-name",
            json={
                "names": ["zzz_var", "aaa_var", "mmm_var"],
                "tax_benefit_model_name": "policyengine-uk",
            },
        )

        assert response.status_code == 200
        names = [v["name"] for v in response.json()]
        assert names == ["aaa_var", "mmm_var", "zzz_var"]

    def test_response_shape_matches_variable_read(self, client, session, uk_version):
        """Returned objects have the same shape as VariableRead."""
        _add_var(session, uk_version, "income_tax", entity="person", description="Tax")

        response = client.post(
            "/variables/by-name",
            json={
                "names": ["income_tax"],
                "tax_benefit_model_name": "policyengine-uk",
            },
        )

        assert response.status_code == 200
        var = response.json()[0]
        assert "id" in var
        assert "name" in var
        assert "entity" in var
        assert "description" in var
        assert "created_at" in var
        assert "tax_benefit_model_version_id" in var


class TestVariablesByNameModelFiltering:
    """Tests for tax_benefit_model_name filtering."""

    def test_model_isolation(self, client, session, uk_version, us_version):
        """Variables from a different model are excluded."""
        _add_var(session, uk_version, "council_tax")
        _add_var(session, us_version, "state_income_tax")

        uk_response = client.post(
            "/variables/by-name",
            json={
                "names": ["council_tax", "state_income_tax"],
                "tax_benefit_model_name": "policyengine-uk",
            },
        )
        us_response = client.post(
            "/variables/by-name",
            json={
                "names": ["council_tax", "state_income_tax"],
                "tax_benefit_model_name": "policyengine-us",
            },
        )

        assert len(uk_response.json()) == 1
        assert uk_response.json()[0]["name"] == "council_tax"
        assert len(us_response.json()) == 1
        assert us_response.json()[0]["name"] == "state_income_tax"


class TestVariablesByNameValidation:
    """Tests for request validation."""

    def test_missing_model_name_returns_422(self, client):
        """Request without tax_benefit_model_name is rejected."""
        response = client.post(
            "/variables/by-name",
            json={"names": ["income_tax"]},
        )

        assert response.status_code == 422

    def test_missing_names_field_returns_422(self, client):
        """Request without names field is rejected."""
        response = client.post(
            "/variables/by-name",
            json={"tax_benefit_model_name": "policyengine-uk"},
        )

        assert response.status_code == 422


class TestVariablesByNameVersionFilter:
    """Tests for version filtering on the by-name endpoint."""

    def test_defaults_to_latest_version(self, client, session):
        """When only model name is given, returns variables from latest version."""
        model = TaxBenefitModel(name="policyengine-uk", description="UK")
        session.add(model)
        session.commit()
        session.refresh(model)

        v1 = TaxBenefitModelVersion(
            model_id=model.id,
            version="1.0",
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        v2 = TaxBenefitModelVersion(
            model_id=model.id,
            version="2.0",
            created_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )
        session.add(v1)
        session.add(v2)
        session.commit()
        session.refresh(v1)
        session.refresh(v2)

        _add_var(session, v1, "old_var")
        _add_var(session, v2, "new_var")

        response = client.post(
            "/variables/by-name",
            json={
                "names": ["old_var", "new_var"],
                "tax_benefit_model_name": "policyengine-uk",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "new_var"

    def test_explicit_version_id_returns_that_version(self, client, session):
        """When version ID is given, returns variables from that specific version."""
        model = TaxBenefitModel(name="policyengine-uk", description="UK")
        session.add(model)
        session.commit()
        session.refresh(model)

        v1 = TaxBenefitModelVersion(
            model_id=model.id,
            version="1.0",
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        v2 = TaxBenefitModelVersion(
            model_id=model.id,
            version="2.0",
            created_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )
        session.add(v1)
        session.add(v2)
        session.commit()
        session.refresh(v1)
        session.refresh(v2)

        _add_var(session, v1, "old_var")
        _add_var(session, v2, "new_var")

        response = client.post(
            "/variables/by-name",
            json={
                "names": ["old_var", "new_var"],
                "tax_benefit_model_name": "policyengine-uk",
                "tax_benefit_model_version_id": str(v1.id),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "old_var"
