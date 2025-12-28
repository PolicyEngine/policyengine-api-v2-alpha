"""Agent endpoint for AI-powered policy analysis.

This endpoint lets users ask natural language questions about tax/benefit policy
and get AI-generated reports using Claude Code connected to the PolicyEngine MCP server.
Outputs are streamed back in real-time via SSE.
"""

import asyncio
import json
import os
from uuid import uuid4

import logfire
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from policyengine_api.config import settings

router = APIRouter(prefix="/agent", tags=["agent"])


class AskRequest(BaseModel):
    """Request to ask a policy question."""

    question: str


class AskResponse(BaseModel):
    """Response with job ID for polling."""

    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    """Status of an agent job."""

    job_id: str
    status: str
    report: str | None = None
    error: str | None = None


# In-memory job storage
_jobs: dict[str, dict] = {}


async def _stream_claude_code(question: str, api_base_url: str):
    """Stream output from Claude Code running with MCP server."""
    # MCP config as JSON string (type: sse for HTTP SSE transport)
    mcp_config = json.dumps(
        {"mcpServers": {"policyengine": {"type": "sse", "url": f"{api_base_url}/mcp"}}}
    )

    # Run Claude Code with streaming JSON output for realtime updates
    process = await asyncio.create_subprocess_exec(
        "claude",
        "-p",
        question,
        "--output-format",
        "stream-json",
        "--verbose",
        "--mcp-config",
        mcp_config,
        "--allowedTools",
        "mcp__policyengine__*,Bash,Read,Grep,Glob,Write,Edit",
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


def _parse_claude_stream_event(line: str) -> dict | None:
    """Parse a Claude Code stream-json event and extract useful content.

    Returns a dict with 'type' and 'content' for streaming to client,
    or None if the event should be skipped.
    """
    if not line or not line.strip():
        return None

    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        # Not JSON, pass through as raw output
        return {"type": "raw", "content": line}

    event_type = event.get("type")

    # Assistant text output (the main response)
    if event_type == "assistant":
        message = event.get("message", {})
        content_blocks = message.get("content", [])
        text_parts = []
        for block in content_blocks:
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool_name = block.get("name", "unknown")
                text_parts.append(f"[Using tool: {tool_name}]")
        if text_parts:
            return {"type": "assistant", "content": "".join(text_parts)}

    # Content block delta (streaming text chunks)
    elif event_type == "content_block_delta":
        delta = event.get("delta", {})
        if delta.get("type") == "text_delta":
            text = delta.get("text", "")
            if text:
                return {"type": "text", "content": text}

    # Tool use events
    elif event_type == "tool_use":
        tool_name = event.get("name", "unknown")
        return {"type": "tool", "content": f"Using tool: {tool_name}"}

    # Tool result
    elif event_type == "tool_result":
        content = event.get("content", "")
        if isinstance(content, str) and content:
            # Truncate long tool results
            preview = content[:500] + "..." if len(content) > 500 else content
            return {"type": "tool_result", "content": preview}

    # Result/completion
    elif event_type == "result":
        result_text = event.get("result", "")
        if result_text:
            return {"type": "result", "content": result_text}

    # System messages
    elif event_type == "system":
        msg = event.get("message", "")
        if msg:
            return {"type": "system", "content": msg}

    return None


async def _stream_modal_sandbox(question: str, api_base_url: str):
    """Stream output from Claude Code running in Modal Sandbox."""
    from concurrent.futures import ThreadPoolExecutor

    with logfire.span(
        "agent_stream", question=question[:100], api_base_url=api_base_url
    ):
        sb = None
        executor = ThreadPoolExecutor(max_workers=2)
        try:
            from policyengine_api.agent_sandbox import run_claude_code_in_sandbox

            logfire.info("creating_sandbox")

            loop = asyncio.get_event_loop()
            sb, process = await loop.run_in_executor(
                executor, run_claude_code_in_sandbox, question, api_base_url
            )
            logfire.info("sandbox_created")

            # Use Modal's async iteration for stdout
            lines_received = 0
            events_sent = 0

            # Modal StreamReader supports async iteration
            async for line in process.stdout:
                lines_received += 1
                logfire.info(
                    "raw_line",
                    line_num=lines_received,
                    line_len=len(line) if line else 0,
                    line_preview=line[:300].replace("session", "sess1on")
                    if line
                    else None,
                )
                parsed = _parse_claude_stream_event(line)
                if parsed:
                    events_sent += 1
                    yield f"data: {json.dumps(parsed)}\n\n"

            # Wait for process
            returncode = await loop.run_in_executor(executor, process.wait)
            logfire.info(
                "complete",
                returncode=returncode,
                events_sent=events_sent,
                lines_received=lines_received,
            )
            yield f"data: {json.dumps({'type': 'done', 'returncode': returncode})}\n\n"

        except Exception as e:
            logfire.exception("failed", error=str(e))
            yield f"data: {json.dumps({'type': 'error', 'content': f'Sandbox error: {str(e)}'})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'returncode': 1})}\n\n"
        finally:
            if sb is not None:
                try:
                    await loop.run_in_executor(executor, sb.terminate)
                except Exception:
                    pass
            executor.shutdown(wait=False)


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
    print(f"[AGENT] /stream called, use_modal={settings.agent_use_modal}", flush=True)
    api_base_url = settings.policyengine_api_url
    logfire.info(
        "stream_analysis: called",
        question=request.question[:100],
        agent_use_modal=settings.agent_use_modal,
        api_base_url=api_base_url,
    )

    if settings.agent_use_modal:
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

    Starts the analysis in the background. Poll GET /agent/status/{job_id} for results.
    For real-time streaming, use POST /agent/stream instead.
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
            if settings.agent_use_modal:
                import modal

                run_policy_analysis = modal.Function.lookup(
                    "policyengine-sandbox", "run_policy_analysis"
                )
                result = run_policy_analysis.remote(request.question, api_base_url)
            else:
                # Run locally
                process = await asyncio.create_subprocess_exec(
                    "claude",
                    "-p",
                    request.question,
                    "--allowedTools",
                    "mcp__policyengine__*,Bash,Read,Grep,Glob,Write,Edit",
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
    """Get the status of an agent job."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = _jobs[job_id]
    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        report=job.get("report"),
        error=job.get("error"),
    )
