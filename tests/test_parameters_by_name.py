"""Tests for POST /parameters/by-name endpoint."""

from test_fixtures.fixtures_parameters import (
    create_parameter,
    model_version,  # noqa: F401 - pytest fixture
)


class TestParametersByName:
    """Tests for looking up parameters by their exact names."""

    def test_returns_matching_parameters(self, client, session, model_version):  # noqa: F811
        """Given known parameter names, returns their full metadata."""
        p1 = create_parameter(session, model_version, "gov.tax.rate", "Tax rate")
        p2 = create_parameter(session, model_version, "gov.tax.threshold", "Threshold")

        response = client.post(
            "/parameters/by-name",
            json={
                "names": ["gov.tax.rate", "gov.tax.threshold"],
                "tax_benefit_model_name": "test-model",
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
                "tax_benefit_model_name": "test-model",
            },
        )

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_empty_list_for_unknown_names(self, client, session, model_version):  # noqa: F811
        """Given names that don't match any parameter, returns an empty list."""
        create_parameter(session, model_version, "gov.exists", "Exists")

        response = client.post(
            "/parameters/by-name",
            json={
                "names": ["gov.does_not_exist", "gov.also_missing"],
                "tax_benefit_model_name": "test-model",
            },
        )

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_only_matching_when_mix_of_known_and_unknown(
        self, client, session, model_version  # noqa: F811
    ):
        """Given a mix of known and unknown names, returns only the known ones."""
        create_parameter(session, model_version, "gov.real", "Real param")

        response = client.post(
            "/parameters/by-name",
            json={
                "names": ["gov.real", "gov.fake"],
                "tax_benefit_model_name": "test-model",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "gov.real"

    def test_filters_by_model_name(self, client, session):
        """Parameters from a different model are excluded."""
        from policyengine_api.models import TaxBenefitModel, TaxBenefitModelVersion

        # Create two models
        model_a = TaxBenefitModel(name="policyengine-uk", description="UK")
        model_b = TaxBenefitModel(name="policyengine-us", description="US")
        session.add(model_a)
        session.add(model_b)
        session.commit()
        session.refresh(model_a)
        session.refresh(model_b)

        ver_a = TaxBenefitModelVersion(
            model_id=model_a.id, version="1.0", description="UK v1"
        )
        ver_b = TaxBenefitModelVersion(
            model_id=model_b.id, version="1.0", description="US v1"
        )
        session.add(ver_a)
        session.add(ver_b)
        session.commit()
        session.refresh(ver_a)
        session.refresh(ver_b)

        # Same parameter name in both models
        create_parameter(session, ver_a, "gov.shared_name", "UK version")
        create_parameter(session, ver_b, "gov.shared_name", "US version")

        # Request only UK
        response = client.post(
            "/parameters/by-name",
            json={
                "names": ["gov.shared_name"],
                "tax_benefit_model_name": "policyengine-uk",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["label"] == "UK version"

    def test_response_shape_matches_parameter_read(
        self, client, session, model_version  # noqa: F811
    ):
        """Returned objects have the same shape as ParameterRead."""
        create_parameter(session, model_version, "gov.shape_test", "Shape test")

        response = client.post(
            "/parameters/by-name",
            json={
                "names": ["gov.shape_test"],
                "tax_benefit_model_name": "test-model",
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

    def test_results_ordered_by_name(self, client, session, model_version):  # noqa: F811
        """Returned parameters are sorted alphabetically by name."""
        create_parameter(session, model_version, "gov.zzz", "Last")
        create_parameter(session, model_version, "gov.aaa", "First")
        create_parameter(session, model_version, "gov.mmm", "Middle")

        response = client.post(
            "/parameters/by-name",
            json={
                "names": ["gov.zzz", "gov.aaa", "gov.mmm"],
                "tax_benefit_model_name": "test-model",
            },
        )

        assert response.status_code == 200
        names = [p["name"] for p in response.json()]
        assert names == ["gov.aaa", "gov.mmm", "gov.zzz"]

    def test_missing_model_name_returns_422(self, client):
        """Request without tax_benefit_model_name is rejected."""
        response = client.post(
            "/parameters/by-name",
            json={"names": ["gov.something"]},
        )

        assert response.status_code == 422

    def test_missing_names_field_returns_422(self, client):
        """Request without names field is rejected."""
        response = client.post(
            "/parameters/by-name",
            json={"tax_benefit_model_name": "test-model"},
        )

        assert response.status_code == 422

    def test_single_name_lookup(self, client, session, model_version):  # noqa: F811
        """Looking up a single parameter name works."""
        create_parameter(session, model_version, "gov.single", "Single param")

        response = client.post(
            "/parameters/by-name",
            json={
                "names": ["gov.single"],
                "tax_benefit_model_name": "test-model",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "gov.single"
