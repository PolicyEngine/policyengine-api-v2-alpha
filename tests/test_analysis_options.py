"""Tests for GET /analysis/options endpoint."""

from policyengine_api.api.module_registry import MODULE_REGISTRY


class TestAnalysisOptions:
    """Tests for the /analysis/options endpoint."""

    def test_returns_all_modules(self, client):
        response = client.get("/analysis/options")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == len(MODULE_REGISTRY)

    def test_response_shape(self, client):
        response = client.get("/analysis/options")
        data = response.json()
        for item in data:
            assert "name" in item
            assert "label" in item
            assert "description" in item
            assert "response_fields" in item
            assert isinstance(item["response_fields"], list)

    def test_filter_by_uk(self, client):
        response = client.get("/analysis/options?country=uk")
        assert response.status_code == 200
        data = response.json()
        names = [m["name"] for m in data]
        assert "constituency" in names
        assert "local_authority" in names
        assert "wealth_decile" in names
        assert "congressional_district" not in names

    def test_filter_by_us(self, client):
        response = client.get("/analysis/options?country=us")
        assert response.status_code == 200
        data = response.json()
        names = [m["name"] for m in data]
        assert "congressional_district" in names
        assert "constituency" not in names
        assert "local_authority" not in names
        assert "wealth_decile" not in names

    def test_shared_modules_in_both_countries(self, client):
        uk_resp = client.get("/analysis/options?country=uk")
        us_resp = client.get("/analysis/options?country=us")
        uk_names = {m["name"] for m in uk_resp.json()}
        us_names = {m["name"] for m in us_resp.json()}
        for shared in ["decile", "poverty", "inequality", "budget_summary", "intra_decile"]:
            assert shared in uk_names
            assert shared in us_names

    def test_unknown_country_returns_empty(self, client):
        response = client.get("/analysis/options?country=fr")
        assert response.status_code == 200
        assert response.json() == []
