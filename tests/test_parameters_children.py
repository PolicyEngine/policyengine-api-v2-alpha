"""Tests for GET /parameters/children endpoint."""


from test_fixtures.fixtures_version_filter import (
    MODEL_NAMES,
    add_params_bulk,
    uk_model,  # noqa: F401
    uk_two_versions,  # noqa: F401
    uk_version,  # noqa: F401
    us_model,  # noqa: F401
    us_version,  # noqa: F401
)

# -----------------------------------------------------------------------------
# Tree structure
# -----------------------------------------------------------------------------


class TestParameterChildrenBasic:
    def test_returns_nodes_for_intermediate_paths(
        self,
        client,
        session,
        uk_version,  # noqa: F811
    ):
        """Parameters at gov.hmrc.x and gov.dwp.x produce nodes for hmrc and dwp."""
        add_params_bulk(
            session,
            uk_version,
            [
                ("gov.hmrc.income_tax.rate", "Basic rate"),
                ("gov.hmrc.income_tax.threshold", "Threshold"),
                ("gov.dwp.uc.amount", "UC amount"),
            ],
        )

        response = client.get(
            "/parameters/children",
            params={
                "tax_benefit_model_name": MODEL_NAMES["UK"],
                "parent_path": "gov",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["parent_path"] == "gov"
        children = data["children"]
        assert len(children) == 2
        paths = [c["path"] for c in children]
        assert paths == ["gov.dwp", "gov.hmrc"]
        for child in children:
            assert child["type"] == "node"
            assert child["child_count"] > 0

    def test_returns_leaf_parameters(
        self,
        client,
        session,
        uk_version,  # noqa: F811
    ):
        """Direct child parameters are returned with type='parameter'."""
        add_params_bulk(
            session,
            uk_version,
            [
                ("gov.benefit_uprating_cpi", "Benefit uprating CPI"),
                ("gov.hmrc.income_tax.rate", "Basic rate"),
            ],
        )

        response = client.get(
            "/parameters/children",
            params={
                "tax_benefit_model_name": MODEL_NAMES["UK"],
                "parent_path": "gov",
            },
        )

        assert response.status_code == 200
        children = response.json()["children"]
        assert len(children) == 2

        leaf = next(c for c in children if c["type"] == "parameter")
        assert leaf["path"] == "gov.benefit_uprating_cpi"
        assert leaf["label"] == "Benefit uprating CPI"
        assert leaf["parameter"] is not None
        assert leaf["parameter"]["name"] == "gov.benefit_uprating_cpi"

        node = next(c for c in children if c["type"] == "node")
        assert node["path"] == "gov.hmrc"

    def test_mixed_nodes_and_leaves(
        self,
        client,
        session,
        uk_version,  # noqa: F811
    ):
        """Both nodes and leaf parameters can appear at the same level."""
        add_params_bulk(
            session,
            uk_version,
            [
                ("gov.hmrc.tax.rate", "Rate"),
                ("gov.flat_rate", "Flat rate"),
                ("gov.threshold", "Threshold"),
            ],
        )

        children = client.get(
            "/parameters/children",
            params={
                "tax_benefit_model_name": MODEL_NAMES["UK"],
                "parent_path": "gov",
            },
        ).json()["children"]

        types = {c["path"]: c["type"] for c in children}
        assert types["gov.hmrc"] == "node"
        assert types["gov.flat_rate"] == "parameter"
        assert types["gov.threshold"] == "parameter"


# -----------------------------------------------------------------------------
# Child counts
# -----------------------------------------------------------------------------


class TestChildCount:
    def test_child_count_reflects_total_descendants(
        self,
        client,
        session,
        uk_version,  # noqa: F811
    ):
        """child_count counts all leaf parameters under the node."""
        add_params_bulk(
            session,
            uk_version,
            [
                ("gov.hmrc.income_tax.rate", "Rate"),
                ("gov.hmrc.income_tax.threshold", "Threshold"),
                ("gov.hmrc.ni.rate", "NI rate"),
            ],
        )

        children = client.get(
            "/parameters/children",
            params={
                "tax_benefit_model_name": MODEL_NAMES["UK"],
                "parent_path": "gov",
            },
        ).json()["children"]

        hmrc = children[0]
        assert hmrc["path"] == "gov.hmrc"
        assert hmrc["child_count"] == 3

    def test_nested_child_count(
        self,
        client,
        session,
        uk_version,  # noqa: F811
    ):
        """Querying a deeper level gives accurate child counts."""
        add_params_bulk(
            session,
            uk_version,
            [
                ("gov.hmrc.income_tax.rate", "Rate"),
                ("gov.hmrc.income_tax.threshold", "Threshold"),
                ("gov.hmrc.ni.rate", "NI rate"),
            ],
        )

        children = client.get(
            "/parameters/children",
            params={
                "tax_benefit_model_name": MODEL_NAMES["UK"],
                "parent_path": "gov.hmrc",
            },
        ).json()["children"]

        assert len(children) == 2
        income_tax = next(c for c in children if c["path"] == "gov.hmrc.income_tax")
        ni = next(c for c in children if c["path"] == "gov.hmrc.ni")
        assert income_tax["child_count"] == 2
        assert ni["child_count"] == 1

    def test_leaf_has_no_child_count(
        self,
        client,
        session,
        uk_version,  # noqa: F811
    ):
        """Leaf parameters have child_count=None."""
        add_params_bulk(session, uk_version, [("gov.rate", "Rate")])

        children = client.get(
            "/parameters/children",
            params={
                "tax_benefit_model_name": MODEL_NAMES["UK"],
                "parent_path": "gov",
            },
        ).json()["children"]

        assert len(children) == 1
        assert children[0]["child_count"] is None


# -----------------------------------------------------------------------------
# Model isolation
# -----------------------------------------------------------------------------


class TestParameterChildrenModelIsolation:
    def test_given_uk_model_then_returns_uk_params(
        self,
        client,
        session,
        uk_version,  # noqa: F811
    ):
        """policyengine-uk returns UK parameters."""
        add_params_bulk(session, uk_version, [("gov.hmrc.rate", "Rate")])

        response = client.get(
            "/parameters/children",
            params={
                "tax_benefit_model_name": MODEL_NAMES["UK"],
                "parent_path": "gov",
            },
        )

        assert response.status_code == 200
        assert len(response.json()["children"]) == 1

    def test_given_us_model_then_returns_us_params(
        self,
        client,
        session,
        us_version,  # noqa: F811
    ):
        """policyengine-us returns US parameters."""
        add_params_bulk(session, us_version, [("gov.irs.rate", "Rate")])

        response = client.get(
            "/parameters/children",
            params={
                "tax_benefit_model_name": MODEL_NAMES["US"],
                "parent_path": "gov",
            },
        )

        assert response.status_code == 200
        assert len(response.json()["children"]) == 1

    def test_given_two_models_then_returns_only_requested(
        self,
        client,
        session,
        uk_version,  # noqa: F811
        us_version,  # noqa: F811
    ):
        """Parameters from a different model are excluded."""
        add_params_bulk(session, uk_version, [("gov.hmrc.rate", "UK rate")])
        add_params_bulk(session, us_version, [("gov.irs.rate", "US rate")])

        uk_paths = [
            c["path"]
            for c in client.get(
                "/parameters/children",
                params={
                    "tax_benefit_model_name": MODEL_NAMES["UK"],
                    "parent_path": "gov",
                },
            ).json()["children"]
        ]
        us_paths = [
            c["path"]
            for c in client.get(
                "/parameters/children",
                params={
                    "tax_benefit_model_name": MODEL_NAMES["US"],
                    "parent_path": "gov",
                },
            ).json()["children"]
        ]

        assert uk_paths == ["gov.hmrc"]
        assert us_paths == ["gov.irs"]


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


class TestParameterChildrenValidation:
    def test_given_missing_model_name_then_422(self, client):
        """Request without tax_benefit_model_name returns 422."""
        response = client.get("/parameters/children", params={"parent_path": "gov"})
        assert response.status_code == 422


# -----------------------------------------------------------------------------
# Edge cases
# -----------------------------------------------------------------------------


class TestParameterChildrenEdgeCases:
    def test_empty_parent_path(
        self,
        client,
        session,
        uk_version,  # noqa: F811
    ):
        """Empty parent_path returns top-level children."""
        add_params_bulk(session, uk_version, [("gov.hmrc.rate", "Rate")])

        response = client.get(
            "/parameters/children",
            params={
                "tax_benefit_model_name": MODEL_NAMES["UK"],
                "parent_path": "",
            },
        )

        assert response.status_code == 200
        children = response.json()["children"]
        assert len(children) == 1
        assert children[0]["path"] == "gov"
        assert children[0]["type"] == "node"

    def test_nonexistent_parent_returns_empty(
        self,
        client,
        session,
        uk_version,  # noqa: F811
    ):
        """A parent path with no descendants returns empty children list."""
        add_params_bulk(session, uk_version, [("gov.hmrc.rate", "Rate")])

        children = client.get(
            "/parameters/children",
            params={
                "tax_benefit_model_name": MODEL_NAMES["UK"],
                "parent_path": "gov.dwp",
            },
        ).json()["children"]

        assert children == []

    def test_children_sorted_by_path(
        self,
        client,
        session,
        uk_version,  # noqa: F811
    ):
        """Children are returned sorted alphabetically by path."""
        add_params_bulk(
            session,
            uk_version,
            [
                ("gov.zzz.param", "Z param"),
                ("gov.aaa.param", "A param"),
                ("gov.mmm.param", "M param"),
            ],
        )

        paths = [
            c["path"]
            for c in client.get(
                "/parameters/children",
                params={
                    "tax_benefit_model_name": MODEL_NAMES["UK"],
                    "parent_path": "gov",
                },
            ).json()["children"]
        ]
        assert paths == ["gov.aaa", "gov.mmm", "gov.zzz"]

    def test_node_label_from_path_segment(
        self,
        client,
        session,
        uk_version,  # noqa: F811
    ):
        """Node labels default to the last path segment."""
        add_params_bulk(session, uk_version, [("gov.hmrc.income_tax.rate", "Rate")])

        children = client.get(
            "/parameters/children",
            params={
                "tax_benefit_model_name": MODEL_NAMES["UK"],
                "parent_path": "gov",
            },
        ).json()["children"]

        assert children[0]["label"] == "hmrc"

    def test_default_parent_path_is_empty(
        self,
        client,
        session,
        uk_version,  # noqa: F811
    ):
        """Omitting parent_path defaults to empty string (root level)."""
        add_params_bulk(session, uk_version, [("gov.hmrc.rate", "Rate")])

        data = client.get(
            "/parameters/children",
            params={"tax_benefit_model_name": MODEL_NAMES["UK"]},
        ).json()

        assert data["parent_path"] == ""
        assert len(data["children"]) == 1

    def test_leaf_parameter_includes_full_metadata(
        self,
        client,
        session,
        uk_version,  # noqa: F811
    ):
        """Leaf parameters include the full ParameterRead shape."""
        add_params_bulk(session, uk_version, [("gov.rate", "The rate")])

        param = client.get(
            "/parameters/children",
            params={
                "tax_benefit_model_name": MODEL_NAMES["UK"],
                "parent_path": "gov",
            },
        ).json()["children"][0]["parameter"]

        assert param["name"] == "gov.rate"
        assert param["label"] == "The rate"
        for field in ("id", "created_at", "tax_benefit_model_version_id"):
            assert field in param

    def test_node_has_no_parameter_field(
        self,
        client,
        session,
        uk_version,  # noqa: F811
    ):
        """Nodes do not include the parameter field."""
        add_params_bulk(session, uk_version, [("gov.hmrc.rate", "Rate")])

        node = client.get(
            "/parameters/children",
            params={
                "tax_benefit_model_name": MODEL_NAMES["UK"],
                "parent_path": "gov",
            },
        ).json()["children"][0]

        assert node["type"] == "node"
        assert node["parameter"] is None

    def test_deep_nesting(
        self,
        client,
        session,
        uk_version,  # noqa: F811
    ):
        """Works correctly with deeply nested parameter paths."""
        add_params_bulk(
            session,
            uk_version,
            [("gov.hmrc.income_tax.rates.uk[0].rate", "Basic rate")],
        )

        for parent, expected_child in [
            ("gov", "gov.hmrc"),
            ("gov.hmrc", "gov.hmrc.income_tax"),
            ("gov.hmrc.income_tax", "gov.hmrc.income_tax.rates"),
            ("gov.hmrc.income_tax.rates", "gov.hmrc.income_tax.rates.uk[0]"),
        ]:
            children = client.get(
                "/parameters/children",
                params={
                    "tax_benefit_model_name": MODEL_NAMES["UK"],
                    "parent_path": parent,
                },
            ).json()["children"]
            assert len(children) == 1
            assert children[0]["path"] == expected_child
            assert children[0]["type"] == "node"

        # Final level should be a leaf
        children = client.get(
            "/parameters/children",
            params={
                "tax_benefit_model_name": MODEL_NAMES["UK"],
                "parent_path": "gov.hmrc.income_tax.rates.uk[0]",
            },
        ).json()["children"]
        assert len(children) == 1
        assert children[0]["type"] == "parameter"
        assert children[0]["path"] == "gov.hmrc.income_tax.rates.uk[0].rate"


# -----------------------------------------------------------------------------
# Version filtering
# -----------------------------------------------------------------------------


class TestParameterChildrenVersionFilter:
    def test_given_model_name_only_then_defaults_to_latest(
        self,
        client,
        session,
        uk_two_versions,  # noqa: F811
    ):
        """When only model name is given, returns children from latest version."""
        v1, v2 = uk_two_versions
        add_params_bulk(session, v1, [("gov.old_param", "Old")])
        add_params_bulk(session, v2, [("gov.new_param", "New")])

        children = client.get(
            "/parameters/children",
            params={
                "tax_benefit_model_name": MODEL_NAMES["UK"],
                "parent_path": "gov",
            },
        ).json()["children"]

        assert len(children) == 1
        assert children[0]["path"] == "gov.new_param"

    def test_given_explicit_version_id_then_returns_that_version(
        self,
        client,
        session,
        uk_two_versions,  # noqa: F811
    ):
        """When version ID is given, returns children from that specific version."""
        v1, v2 = uk_two_versions
        add_params_bulk(session, v1, [("gov.old_param", "Old")])
        add_params_bulk(session, v2, [("gov.new_param", "New")])

        children = client.get(
            "/parameters/children",
            params={
                "tax_benefit_model_name": MODEL_NAMES["UK"],
                "parent_path": "gov",
                "tax_benefit_model_version_id": str(v1.id),
            },
        ).json()["children"]

        assert len(children) == 1
        assert children[0]["path"] == "gov.old_param"
