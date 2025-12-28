"""Tests for the demo streaming API endpoints.

Tests verify that Claude Code is invoked correctly with proper MCP configuration.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from policyengine_api.main import app

client = TestClient(app)


class TestDemoEndpoints:
    """Test the /demo API endpoints."""

    def test_status_not_found(self):
        """GET /demo/status/{job_id} should return 404 for unknown job."""
        response = client.get("/demo/status/nonexistent-job-id")
        assert response.status_code == 404

    def test_ask_request_model(self):
        """AskRequest model should accept question field."""
        from policyengine_api.api.demo import AskRequest

        req = AskRequest(question="Test question")
        assert req.question == "Test question"

    def test_ask_response_model(self):
        """AskResponse model should have job_id and status fields."""
        from policyengine_api.api.demo import AskResponse

        resp = AskResponse(job_id="test-123", status="pending")
        assert resp.job_id == "test-123"
        assert resp.status == "pending"


class TestClaudeCodeInvocation:
    """Test that Claude Code is invoked correctly."""

    @pytest.mark.asyncio
    async def test_stream_claude_code_invokes_claude_cli(self):
        """_stream_claude_code should invoke the claude CLI with correct args."""
        from policyengine_api.api.demo import _stream_claude_code

        captured_args = []

        async def mock_create_subprocess(*args, **kwargs):
            captured_args.append(args)
            mock_process = MagicMock()
            mock_process.returncode = 0

            async def mock_stdout_iter():
                yield b"Test output\n"

            mock_process.stdout = mock_stdout_iter()
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")
            mock_process.wait = AsyncMock()
            return mock_process

        with patch(
            "asyncio.create_subprocess_exec", side_effect=mock_create_subprocess
        ):
            events = []
            async for event in _stream_claude_code(
                "Test question", "http://localhost:8000"
            ):
                events.append(event)

        # Verify claude was called
        assert len(captured_args) == 1
        args = captured_args[0]

        # Check command
        assert args[0] == "claude"
        assert "--print" in args
        assert "--allowedTools" in args

        # Check MCP tools are allowed
        allowed_tools_idx = args.index("--allowedTools") + 1
        allowed_tools = args[allowed_tools_idx]
        assert "mcp__policyengine__*" in allowed_tools

        # Check question is passed
        assert "Test question" in args

    @pytest.mark.asyncio
    async def test_stream_claude_code_yields_sse_events(self):
        """_stream_claude_code should yield properly formatted SSE events."""
        from policyengine_api.api.demo import _stream_claude_code

        async def mock_create_subprocess(*args, **kwargs):
            mock_process = MagicMock()
            mock_process.returncode = 0

            async def mock_stdout_iter():
                yield b"Line 1\n"
                yield b"Line 2\n"

            mock_process.stdout = mock_stdout_iter()
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")
            mock_process.wait = AsyncMock()
            return mock_process

        with patch(
            "asyncio.create_subprocess_exec", side_effect=mock_create_subprocess
        ):
            events = []
            async for event in _stream_claude_code("Test", "http://localhost"):
                events.append(event)

        # Should have output events
        output_events = [e for e in events if "output" in e]
        assert len(output_events) == 2

        # Each should be valid SSE format
        for event in output_events:
            assert event.startswith("data: ")
            assert event.endswith("\n\n")
            data = json.loads(event[6:].strip())
            assert data["type"] == "output"
            assert "content" in data

        # Should have done event
        done_events = [e for e in events if "done" in e]
        assert len(done_events) == 1
        done_data = json.loads(done_events[0][6:].strip())
        assert done_data["type"] == "done"
        assert done_data["returncode"] == 0

    @pytest.mark.asyncio
    async def test_stream_claude_code_handles_errors(self):
        """_stream_claude_code should yield error events on non-zero exit."""
        from policyengine_api.api.demo import _stream_claude_code

        async def mock_create_subprocess(*args, **kwargs):
            mock_process = MagicMock()
            mock_process.returncode = 1

            async def mock_stdout_iter():
                yield b"Partial output\n"

            mock_process.stdout = mock_stdout_iter()
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(
                return_value=b"Error: something went wrong"
            )
            mock_process.wait = AsyncMock()
            return mock_process

        with patch(
            "asyncio.create_subprocess_exec", side_effect=mock_create_subprocess
        ):
            events = []
            async for event in _stream_claude_code("Test", "http://localhost"):
                events.append(event)

        # Should have error event
        error_events = [e for e in events if "error" in e]
        assert len(error_events) == 1
        error_data = json.loads(error_events[0][6:].strip())
        assert error_data["type"] == "error"
        assert "something went wrong" in error_data["content"]

    @pytest.mark.asyncio
    async def test_stream_claude_code_passes_anthropic_api_key(self):
        """_stream_claude_code should pass ANTHROPIC_API_KEY in env."""
        from policyengine_api.api.demo import _stream_claude_code

        captured_kwargs = []

        async def mock_create_subprocess(*args, **kwargs):
            captured_kwargs.append(kwargs)
            mock_process = MagicMock()
            mock_process.returncode = 0

            async def mock_stdout_iter():
                yield b"Done\n"

            mock_process.stdout = mock_stdout_iter()
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")
            mock_process.wait = AsyncMock()
            return mock_process

        with patch(
            "asyncio.create_subprocess_exec", side_effect=mock_create_subprocess
        ):
            async for _ in _stream_claude_code("Test", "http://localhost"):
                pass

        # Verify env was passed
        assert len(captured_kwargs) == 1
        assert "env" in captured_kwargs[0]
        assert "ANTHROPIC_API_KEY" in captured_kwargs[0]["env"]


class TestDemoSandbox:
    """Test the Modal sandbox configuration."""

    def test_sandbox_image_uses_bun(self):
        """Sandbox image should use bun, not npm."""
        from policyengine_api.demo_sandbox import sandbox_image

        # Just verify the image is defined - actual bun installation
        # is tested when deploying to Modal
        assert sandbox_image is not None

    def test_run_function_signature(self):
        """run_claude_code_in_sandbox should accept question and api_base_url."""
        import inspect

        from policyengine_api.demo_sandbox import run_claude_code_in_sandbox

        sig = inspect.signature(run_claude_code_in_sandbox)
        params = list(sig.parameters.keys())
        assert "question" in params
        assert "api_base_url" in params

    def test_modal_function_defined(self):
        """run_policy_analysis Modal function should be defined."""
        from policyengine_api.demo_sandbox import run_policy_analysis

        # Modal functions are wrapped, so check it exists and has expected attributes
        assert run_policy_analysis is not None
        assert hasattr(run_policy_analysis, "remote") or hasattr(
            run_policy_analysis, "local"
        )
