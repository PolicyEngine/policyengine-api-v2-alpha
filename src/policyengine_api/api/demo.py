"""Demo endpoint for AI-powered policy analysis.

This endpoint lets users ask natural language questions about tax/benefit policy
and get AI-generated reports using Claude Code connected to the PolicyEngine MCP server.
Outputs are streamed back in real-time via SSE.
"""

import asyncio
import json
import os
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from policyengine_api.config import settings

router = APIRouter(prefix="/demo", tags=["demo"])


class AskRequest(BaseModel):
    """Request to ask a policy question."""

    question: str


class AskResponse(BaseModel):
    """Response with job ID for polling."""

    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    """Status of a demo job."""

    job_id: str
    status: str
    report: str | None = None
    error: str | None = None


# In-memory job storage
_jobs: dict[str, dict] = {}


async def _stream_claude_code(question: str, api_base_url: str):
    """Stream output from Claude Code running with MCP server."""
    # Write MCP config for Claude Code
    claude_dir = os.path.expanduser("~/.claude")
    os.makedirs(claude_dir, exist_ok=True)

    mcp_config = {
        "mcpServers": {"policyengine": {"type": "url", "url": f"{api_base_url}/mcp/"}}
    }
    config_path = os.path.join(claude_dir, "mcp_servers.json")
    with open(config_path, "w") as f:
        json.dump(mcp_config, f)

    # Run Claude Code with streaming
    process = await asyncio.create_subprocess_exec(
        "claude",
        "--print",
        "--allowedTools",
        "mcp__policyengine__*,Bash,Read,Grep,Glob,Write,Edit",
        question,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "ANTHROPIC_API_KEY": settings.anthropic_api_key},
    )

    # Stream stdout
    async for line in process.stdout:
        text = line.decode("utf-8")
        yield f"data: {json.dumps({'type': 'output', 'content': text})}\n\n"

    # Wait for completion
    await process.wait()

    if process.returncode != 0:
        stderr = await process.stderr.read()
        yield f"data: {json.dumps({'type': 'error', 'content': stderr.decode('utf-8')})}\n\n"

    yield f"data: {json.dumps({'type': 'done', 'returncode': process.returncode})}\n\n"


async def _stream_modal_sandbox(question: str, api_base_url: str):
    """Stream output from Claude Code running in Modal Sandbox."""

    from policyengine_api.demo_sandbox import run_claude_code_in_sandbox

    sb, process = run_claude_code_in_sandbox(question, api_base_url)

    try:
        # Stream stdout line by line
        for line in process.stdout:
            yield f"data: {json.dumps({'type': 'output', 'content': line})}\n\n"

        process.wait()

        if process.returncode != 0:
            stderr = process.stderr.read()
            yield f"data: {json.dumps({'type': 'error', 'content': stderr})}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'returncode': process.returncode})}\n\n"
    finally:
        sb.terminate()


@router.post("/stream")
async def stream_analysis(request: AskRequest):
    """Stream a policy analysis using Claude Code with MCP.

    Returns a Server-Sent Events stream with real-time output from Claude Code.

    Event types:
    - output: A line of output from Claude Code
    - error: An error message
    - done: Analysis complete (includes returncode)

    Example:
    ```
    data: {"type": "output", "content": "Searching for basic rate parameter...\\n"}

    data: {"type": "output", "content": "Found parameter: gov.hmrc.income_tax.rates.uk[0].rate\\n"}

    data: {"type": "done", "returncode": 0}
    ```
    """
    api_base_url = settings.policyengine_api_url

    if settings.demo_use_modal:
        return StreamingResponse(
            _stream_modal_sandbox(request.question, api_base_url),
            media_type="text/event-stream",
        )
    else:
        return StreamingResponse(
            _stream_claude_code(request.question, api_base_url),
            media_type="text/event-stream",
        )


@router.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest) -> AskResponse:
    """Ask a policy question (non-streaming).

    Starts the analysis in the background. Poll GET /demo/status/{job_id} for results.
    For real-time streaming, use POST /demo/stream instead.
    """
    job_id = str(uuid4())
    api_base_url = settings.policyengine_api_url

    _jobs[job_id] = {
        "status": "pending",
        "question": request.question,
        "report": None,
        "error": None,
    }

    # Run in background
    async def run_job():
        _jobs[job_id]["status"] = "running"
        try:
            if settings.demo_use_modal:
                import modal

                run_policy_analysis = modal.Function.lookup(
                    "policyengine-sandbox", "run_policy_analysis"
                )
                result = run_policy_analysis.remote(request.question, api_base_url)
            else:
                # Run locally
                process = await asyncio.create_subprocess_exec(
                    "claude",
                    "--print",
                    "--allowedTools",
                    "mcp__policyengine__*,Bash,Read,Grep,Glob,Write,Edit",
                    request.question,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env={**os.environ, "ANTHROPIC_API_KEY": settings.anthropic_api_key},
                )
                stdout, stderr = await process.communicate()
                result = {
                    "status": "completed" if process.returncode == 0 else "failed",
                    "report": stdout.decode("utf-8"),
                    "error": stderr.decode("utf-8")
                    if process.returncode != 0
                    else None,
                }

            _jobs[job_id]["status"] = result.get("status", "completed")
            _jobs[job_id]["report"] = result.get("report")
            _jobs[job_id]["error"] = result.get("error")
        except Exception as e:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(e)

    asyncio.create_task(run_job())
    return AskResponse(job_id=job_id, status="pending")


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """Get the status of a demo job."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = _jobs[job_id]
    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        report=job.get("report"),
        error=job.get("error"),
    )
