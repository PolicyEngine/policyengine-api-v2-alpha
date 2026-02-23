"""Tests for GET /analysis/options endpoint."""

from policyengine_api.api.module_registry import MODULE_REGISTRY, get_modules_for_country


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

    def test_all_names_are_strings(self, client):
        response = client.get("/analysis/options")
        for item in response.json():
            assert isinstance(item["name"], str)
            assert len(item["name"]) > 0

    def test_all_labels_are_non_empty(self, client):
        response = client.get("/analysis/options")
        for item in response.json():
            assert isinstance(item["label"], str)
            assert len(item["label"]) > 0

    def test_all_descriptions_are_non_empty(self, client):
        response = client.get("/analysis/options")
        for item in response.json():
            assert isinstance(item["description"], str)
            assert len(item["description"]) > 0

    def test_all_response_fields_are_non_empty_lists(self, client):
        response = client.get("/analysis/options")
        for item in response.json():
            assert len(item["response_fields"]) > 0
            for field in item["response_fields"]:
                assert isinstance(field, str)

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

    def test_uk_count_matches_registry(self, client):
        response = client.get("/analysis/options?country=uk")
        data = response.json()
        expected = len(get_modules_for_country("uk"))
        assert len(data) == expected

    def test_us_count_matches_registry(self, client):
        response = client.get("/analysis/options?country=us")
        data = response.json()
        expected = len(get_modules_for_country("us"))
        assert len(data) == expected

    def test_shared_modules_in_both_countries(self, client):
        uk_resp = client.get("/analysis/options?country=uk")
        us_resp = client.get("/analysis/options?country=us")
        uk_names = {m["name"] for m in uk_resp.json()}
        us_names = {m["name"] for m in us_resp.json()}
        for shared in [
            "decile",
            "poverty",
            "inequality",
            "budget_summary",
            "intra_decile",
            "program_statistics",
        ]:
            assert shared in uk_names
            assert shared in us_names

    def test_unknown_country_returns_empty(self, client):
        response = client.get("/analysis/options?country=fr")
        assert response.status_code == 200
        assert response.json() == []

    def test_program_statistics_has_two_response_fields(self, client):
        response = client.get("/analysis/options")
        ps_module = next(
            m for m in response.json() if m["name"] == "program_statistics"
        )
        assert "program_statistics" in ps_module["response_fields"]
        assert "detailed_budget" in ps_module["response_fields"]

    def test_wealth_decile_has_two_response_fields(self, client):
        response = client.get("/analysis/options?country=uk")
        wd_module = next(m for m in response.json() if m["name"] == "wealth_decile")
        assert "wealth_decile" in wd_module["response_fields"]
        assert "intra_wealth_decile" in wd_module["response_fields"]

    def test_no_country_param_returns_all(self, client):
        all_resp = client.get("/analysis/options")
        data = all_resp.json()
        returned_names = {m["name"] for m in data}
        assert returned_names == set(MODULE_REGISTRY.keys())

    def test_response_matches_registry_data(self, client):
        response = client.get("/analysis/options")
        for item in response.json():
            registry_mod = MODULE_REGISTRY[item["name"]]
            assert item["label"] == registry_mod.label
            assert item["description"] == registry_mod.description
            assert item["response_fields"] == list(registry_mod.response_fields)
