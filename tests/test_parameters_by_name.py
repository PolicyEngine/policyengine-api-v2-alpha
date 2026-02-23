"""Tests for POST /parameters/by-name endpoint."""

import pytest

from policyengine_api.models import (
    Parameter,
    TaxBenefitModel,
    TaxBenefitModelVersion,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


def create_parameter(session, model_version, name: str, label: str) -> Parameter:
    """Create and persist a Parameter."""
    param = Parameter(
        name=name,
        label=label,
        tax_benefit_model_version_id=model_version.id,
    )
    session.add(param)
    session.commit()
    session.refresh(param)
    return param


class TestParametersByName:
    """Tests for looking up parameters by their exact names."""

    def test_returns_matching_parameters(self, client, session, us_version):
        """Given known parameter names, returns their full metadata."""
        create_parameter(session, us_version, "gov.tax.rate", "Tax rate")
        create_parameter(session, us_version, "gov.tax.threshold", "Threshold")

        response = client.post(
            "/parameters/by-name",
            json={
                "names": ["gov.tax.rate", "gov.tax.threshold"],
                "country_id": "us",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        returned_names = {p["name"] for p in data}
        assert returned_names == {"gov.tax.rate", "gov.tax.threshold"}

    def test_returns_empty_list_for_empty_names(self, client):
        """Given an empty names list, returns an empty list."""
        response = client.post(
            "/parameters/by-name",
            json={
                "names": [],
                "country_id": "us",
            },
        )

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_empty_list_for_unknown_names(self, client, session, us_version):
        """Given names that don't match any parameter, returns an empty list."""
        create_parameter(session, us_version, "gov.exists", "Exists")

        response = client.post(
            "/parameters/by-name",
            json={
                "names": ["gov.does_not_exist", "gov.also_missing"],
                "country_id": "us",
            },
        )

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_only_matching_when_mix_of_known_and_unknown(
        self, client, session, us_version
    ):
        """Given a mix of known and unknown names, returns only the known ones."""
        create_parameter(session, us_version, "gov.real", "Real param")

        response = client.post(
            "/parameters/by-name",
            json={
                "names": ["gov.real", "gov.fake"],
                "country_id": "us",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "gov.real"

    def test_filters_by_country(self, client, session):
        """Parameters from a different country are excluded."""
        # Create two models
        model_uk = TaxBenefitModel(name="policyengine-uk", description="UK")
        model_us = TaxBenefitModel(name="policyengine-us", description="US")
        session.add(model_uk)
        session.add(model_us)
        session.commit()
        session.refresh(model_uk)
        session.refresh(model_us)

        ver_uk = TaxBenefitModelVersion(
            model_id=model_uk.id, version="1.0", description="UK v1"
        )
        ver_us = TaxBenefitModelVersion(
            model_id=model_us.id, version="1.0", description="US v1"
        )
        session.add(ver_uk)
        session.add(ver_us)
        session.commit()
        session.refresh(ver_uk)
        session.refresh(ver_us)

        # Same parameter name in both models
        create_parameter(session, ver_uk, "gov.shared_name", "UK version")
        create_parameter(session, ver_us, "gov.shared_name", "US version")

        # Request only UK
        response = client.post(
            "/parameters/by-name",
            json={
                "names": ["gov.shared_name"],
                "country_id": "uk",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["label"] == "UK version"

    def test_response_shape_matches_parameter_read(
        self, client, session, us_version
    ):
        """Returned objects have the same shape as ParameterRead."""
        create_parameter(session, us_version, "gov.shape_test", "Shape test")

        response = client.post(
            "/parameters/by-name",
            json={
                "names": ["gov.shape_test"],
                "country_id": "us",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        param = data[0]
        assert "id" in param
        assert "name" in param
        assert "label" in param
        assert "created_at" in param
        assert "tax_benefit_model_version_id" in param

    def test_results_ordered_by_name(self, client, session, us_version):
        """Returned parameters are sorted alphabetically by name."""
        create_parameter(session, us_version, "gov.zzz", "Last")
        create_parameter(session, us_version, "gov.aaa", "First")
        create_parameter(session, us_version, "gov.mmm", "Middle")

        response = client.post(
            "/parameters/by-name",
            json={
                "names": ["gov.zzz", "gov.aaa", "gov.mmm"],
                "country_id": "us",
            },
        )

        assert response.status_code == 200
        names = [p["name"] for p in response.json()]
        assert names == ["gov.aaa", "gov.mmm", "gov.zzz"]

    def test_missing_country_id_returns_422(self, client):
        """Request without country_id is rejected."""
        response = client.post(
            "/parameters/by-name",
            json={"names": ["gov.something"]},
        )

        assert response.status_code == 422

    def test_invalid_country_id_returns_422(self, client):
        """Request with invalid country_id is rejected."""
        response = client.post(
            "/parameters/by-name",
            json={"names": ["gov.something"], "country_id": "invalid"},
        )

        assert response.status_code == 422

    def test_missing_names_field_returns_422(self, client):
        """Request without names field is rejected."""
        response = client.post(
            "/parameters/by-name",
            json={"country_id": "us"},
        )

        assert response.status_code == 422

    def test_single_name_lookup(self, client, session, us_version):
        """Looking up a single parameter name works."""
        create_parameter(session, us_version, "gov.single", "Single param")

        response = client.post(
            "/parameters/by-name",
            json={
                "names": ["gov.single"],
                "country_id": "us",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "gov.single"
