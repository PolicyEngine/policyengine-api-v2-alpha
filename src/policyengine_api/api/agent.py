"""Agent endpoint for AI-powered policy analysis.

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


async def _stream_modal_sandbox(question: str, api_base_url: str):
    """Stream output from Claude Code running in Modal Sandbox."""
    from concurrent.futures import ThreadPoolExecutor

    import logfire

    sb = None
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        from policyengine_api.agent_sandbox import run_claude_code_in_sandbox

        logfire.info(
            "Creating Modal sandbox", question=question[:100], api_base_url=api_base_url
        )

        # Run blocking Modal SDK calls in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        sb, process = await loop.run_in_executor(
            executor, run_claude_code_in_sandbox, question, api_base_url
        )
        logfire.info("Modal sandbox created, streaming output")

        # Poll for lines with timeout to allow other async tasks
        import queue
        import threading

        line_queue = queue.Queue()

        def stream_reader():
            try:
                logfire.info("stream_reader: starting to read stdout")
                line_count = 0
                for line in process.stdout:
                    line_count += 1
                    logfire.info(
                        "stream_reader: got line",
                        line_num=line_count,
                        line_preview=line[:200] if line else None,
                    )
                    line_queue.put(("line", line))
                logfire.info("stream_reader: stdout exhausted, waiting for process")
                process.wait()
                logfire.info(
                    "stream_reader: process finished", returncode=process.returncode
                )
                if process.returncode != 0:
                    stderr = process.stderr.read()
                    logfire.error(
                        "stream_reader: process failed",
                        returncode=process.returncode,
                        stderr=stderr[:500] if stderr else None,
                    )
                    line_queue.put(("error", (process.returncode, stderr)))
                else:
                    line_queue.put(("done", process.returncode))
            except Exception as e:
                logfire.exception("stream_reader: exception", error=str(e))
                line_queue.put(("exception", str(e)))

        logfire.info("_stream_modal_sandbox: starting reader thread")
        reader_thread = threading.Thread(target=stream_reader, daemon=True)
        reader_thread.start()
        logfire.info("_stream_modal_sandbox: reader thread started, entering main loop")

        while True:
            try:
                # Non-blocking check with short timeout
                item = await loop.run_in_executor(
                    executor, lambda: line_queue.get(timeout=0.1)
                )
                event_type, data = item

                if event_type == "line":
                    yield f"data: {json.dumps({'type': 'output', 'content': data})}\n\n"
                elif event_type == "error":
                    returncode, stderr = data
                    logfire.error(
                        "Claude Code failed in sandbox",
                        returncode=returncode,
                        stderr=stderr[:500],
                    )
                    yield f"data: {json.dumps({'type': 'error', 'content': stderr})}\n\n"
                    yield f"data: {json.dumps({'type': 'done', 'returncode': returncode})}\n\n"
                    break
                elif event_type == "done":
                    yield f"data: {json.dumps({'type': 'done', 'returncode': data})}\n\n"
                    break
                elif event_type == "exception":
                    raise Exception(data)
            except Exception as e:
                if "Empty" in type(e).__name__:
                    # Queue timeout, continue polling
                    await asyncio.sleep(0)
                    continue
                raise

    except Exception as e:
        logfire.exception("Modal sandbox failed", error=str(e))
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
    api_base_url = settings.policyengine_api_url

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
