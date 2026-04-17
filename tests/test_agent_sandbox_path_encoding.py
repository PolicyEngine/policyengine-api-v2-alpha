"""Regression test for path-parameter URL encoding in the agent sandbox (#273)."""

from unittest.mock import MagicMock, patch

from policyengine_api.agent_sandbox import execute_api_tool


def test_path_parameter_is_url_encoded():
    """Values containing '/' must not escape the intended path segment."""
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {"ok": True}

    tool = {
        "_meta": {
            "path": "/widgets/{widget_id}",
            "method": "get",
            "parameters": [{"name": "widget_id", "in": "path"}],
        }
    }

    with patch(
        "policyengine_api.agent_sandbox.requests.get", return_value=fake_resp
    ) as mock_get:
        execute_api_tool(
            tool=tool,
            tool_input={"widget_id": "abc/def#frag"},
            api_base_url="https://example.test",
            log_fn=lambda msg: None,
        )

    args, _ = mock_get.call_args
    url = args[0]
    assert url == "https://example.test/widgets/abc%2Fdef%23frag"
