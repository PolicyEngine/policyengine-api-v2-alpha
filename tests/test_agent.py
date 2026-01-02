"""Tests for the agent API endpoints.

Tests verify the agent endpoint structure and integration with Claude Agent SDK.
"""

import pytest
from fastapi.testclient import TestClient

from policyengine_api.main import app

pytestmark = pytest.mark.integration

client = TestClient(app)


class TestAgentEndpoints:
    """Test the /agent API endpoints."""

    def test_status_not_found(self):
        """GET /agent/status/{job_id} should return 404 for unknown job."""
        response = client.get("/agent/status/nonexistent-job-id")
        assert response.status_code == 404

    def test_run_request_model(self):
        """RunRequest model should accept question field."""
        from policyengine_api.api.agent import RunRequest

        req = RunRequest(question="Test question")
        assert req.question == "Test question"

    def test_run_response_model(self):
        """RunResponse model should have call_id and status fields."""
        from policyengine_api.api.agent import RunResponse

        resp = RunResponse(call_id="fc-test123", status="running")
        assert resp.call_id == "fc-test123"
        assert resp.status == "running"

    def test_logs_not_found(self):
        """GET /agent/logs/{call_id} should return 404 for unknown call."""
        response = client.get("/agent/logs/nonexistent-call-id")
        assert response.status_code == 404


class TestAgentSandbox:
    """Test the Modal agent sandbox configuration."""

    def test_run_agent_function_signature(self):
        """run_agent should accept expected parameters."""
        import inspect

        from policyengine_api.agent_sandbox import run_agent

        sig = inspect.signature(run_agent.local)
        params = list(sig.parameters.keys())
        assert "question" in params
        assert "api_base_url" in params
        assert "call_id" in params
        assert "history" in params

    def test_modal_function_defined(self):
        """run_agent Modal function should be defined."""
        from policyengine_api.agent_sandbox import run_agent

        assert run_agent is not None
        assert hasattr(run_agent, "remote") or hasattr(run_agent, "local")

    def test_system_prompt_defined(self):
        """System prompt should be defined with key instructions."""
        from policyengine_api.agent_sandbox import SYSTEM_PROMPT

        assert "policyengine-uk" in SYSTEM_PROMPT
        assert "policyengine-us" in SYSTEM_PROMPT
        assert "filter by country" in SYSTEM_PROMPT.lower()
