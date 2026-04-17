"""Agent endpoint for AI-powered policy analysis.

This endpoint lets users ask natural language questions about tax/benefit policy
and get AI-generated reports using Claude Code connected to the PolicyEngine MCP server.

The agent runs in a Modal sandbox (production) or locally (development).
"""

import asyncio
from datetime import datetime

import logfire
from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from pydantic import BaseModel

from policyengine_api.config import settings
from policyengine_api.security import issue_signed_call_id, verified_call_id


def get_traceparent() -> str | None:
    """Get the current W3C traceparent header for distributed tracing."""
    carrier: dict[str, str] = {}
    TraceContextTextMapPropagator().inject(carrier)
    return carrier.get("traceparent")


router = APIRouter(prefix="/agent", tags=["agent"])


class ConversationMessage(BaseModel):
    """A message in the conversation history."""

    role: str  # "user" or "assistant"
    content: str


class RunRequest(BaseModel):
    """Request to run the agent."""

    question: str
    history: list[ConversationMessage] = []


class RunResponse(BaseModel):
    """Response with function call ID for fetching logs."""

    call_id: str
    status: str


class LogEntry(BaseModel):
    """A single log entry."""

    timestamp: str
    message: str


class LogsResponse(BaseModel):
    """Response with logs for a function call."""

    call_id: str
    status: str  # "running", "completed", "failed"
    logs: list[LogEntry]
    result: dict | None = None


class LogInput(BaseModel):
    """Input for logging an entry."""

    message: str


class StatusResponse(BaseModel):
    """Response with job status."""

    call_id: str
    status: str
    result: dict | None = None


# In-memory storage for function calls and their logs. Bounded so a flood of
# spawn requests cannot drive the process OOM; entries expire after
# ``_CALL_TTL_SECONDS`` of inactivity.
_MAX_ACTIVE_CALLS = 2048
_CALL_TTL_SECONDS = 60 * 60  # 1 hour

_calls: TTLCache[str, dict] = TTLCache(maxsize=_MAX_ACTIVE_CALLS, ttl=_CALL_TTL_SECONDS)
_logs: TTLCache[str, list[LogEntry]] = TTLCache(
    maxsize=_MAX_ACTIVE_CALLS, ttl=_CALL_TTL_SECONDS
)


def _run_local_agent(
    call_id: str,
    question: str,
    api_base_url: str,
    history: list[ConversationMessage] | None = None,
) -> None:
    """Run agent locally in a background thread."""
    from policyengine_api.agent_sandbox import _run_agent_impl

    try:
        history_dicts = [
            {"role": m.role, "content": m.content} for m in (history or [])
        ]
        result = _run_agent_impl(question, api_base_url, call_id, history_dicts)
        _calls[call_id]["status"] = result.get("status", "completed")
        _calls[call_id]["result"] = result
    except Exception as e:
        _calls[call_id]["status"] = "failed"
        _calls[call_id]["result"] = {"status": "failed", "error": str(e)}


@router.post("/run", response_model=RunResponse)
async def run_agent(request: RunRequest) -> RunResponse:
    """Start the agent to answer a policy question.

    Returns a call_id that can be used to fetch logs and status.

    Example:
    ```bash
    curl -X POST https://v2.api.policyengine.org/agent/run \\
      -H "Content-Type: application/json" \\
      -d '{"question": "What is the UK basic rate of income tax?"}'
    ```

    Response:
    ```json
    {"call_id": "fc-abc123", "status": "running"}
    ```

    Then poll /agent/logs/{call_id} to get logs and final result.
    """
    logfire.info("agent_run", question=request.question[:100])

    api_base_url = settings.policyengine_api_url
    # Signed id: the public path segment doubles as a bearer token for the
    # downstream ``/agent/log/{id}`` and ``/agent/complete/{id}`` callbacks.
    call_id = issue_signed_call_id()

    # Initialize logs storage
    _logs[call_id] = []

    if settings.agent_use_modal:
        # Production: use Modal
        import modal

        traceparent = get_traceparent()
        run_fn = modal.Function.from_name("policyengine-sandbox", "run_agent")
        history_dicts = [
            {"role": m.role, "content": m.content} for m in request.history
        ]
        call = run_fn.spawn(
            request.question,
            api_base_url,
            call_id,
            history_dicts,
            traceparent=traceparent,
        )

        _calls[call_id] = {
            "call": call,
            "modal_call_id": call.object_id,
            "question": request.question,
            "started_at": datetime.utcnow().isoformat(),
            "status": "running",
            "result": None,
            "trace_id": traceparent,  # Store for linking
        }
        logfire.info("agent_spawned", call_id=call_id, modal_call_id=call.object_id)
    else:
        # Local development: run in background thread
        _calls[call_id] = {
            "call": None,
            "modal_call_id": None,
            "question": request.question,
            "started_at": datetime.utcnow().isoformat(),
            "status": "running",
            "result": None,
        }
        logfire.info("agent_spawned_local", call_id=call_id)

        # Run in background using the currently-running event loop. The
        # endpoint is already ``async def`` so a loop is always available;
        # ``get_event_loop`` is deprecated outside of a running loop and was
        # emitting DeprecationWarnings on every invocation.
        loop = asyncio.get_running_loop()
        loop.run_in_executor(
            None,
            _run_local_agent,
            call_id,
            request.question,
            api_base_url,
            request.history,
        )

    return RunResponse(call_id=call_id, status="running")


@router.post("/log/{call_id}")
async def post_log(
    log_input: LogInput,
    call_id: str = Depends(verified_call_id),
) -> dict:
    """Receive a log entry from the running agent.

    This endpoint is called by the Modal function to stream logs back.
    The ``call_id`` must be a signed identifier issued by ``/agent/run``.
    """
    if call_id not in _logs:
        _logs[call_id] = []

    entry = LogEntry(
        timestamp=datetime.utcnow().isoformat(),
        message=log_input.message,
    )
    _logs[call_id].append(entry)

    return {"status": "ok"}


@router.post("/complete/{call_id}")
async def complete_call(
    result: dict,
    call_id: str = Depends(verified_call_id),
) -> dict:
    """Mark a call as complete with its result.

    Called by the Modal function when it finishes. The ``call_id`` must
    be a signed identifier issued by ``/agent/run``.
    """
    if call_id in _calls:
        _calls[call_id]["status"] = result.get("status", "completed")
        _calls[call_id]["result"] = result

    return {"status": "ok"}


@router.get("/logs/{call_id}", response_model=LogsResponse)
async def get_logs(call_id: str) -> LogsResponse:
    """Get logs for an agent run.

    Returns all logs emitted so far, plus status and result if completed.

    Example:
    ```bash
    curl https://v2.api.policyengine.org/agent/logs/fc-abc123
    ```
    """
    logfire.info("agent_get_logs", call_id=call_id)

    if call_id not in _calls:
        raise HTTPException(status_code=404, detail="Call not found")

    call_info = _calls[call_id]
    logs = _logs.get(call_id, [])

    return LogsResponse(
        call_id=call_id,
        status=call_info["status"],
        logs=logs,
        result=call_info["result"],
    )


@router.get("/status/{call_id}", response_model=StatusResponse)
async def get_status(call_id: str) -> StatusResponse:
    """Get just the status of an agent run (no logs).

    Faster than /logs if you just need to check if it's done.
    """
    logfire.info("agent_get_status", call_id=call_id)

    if call_id not in _calls:
        raise HTTPException(status_code=404, detail="Call not found")

    call_info = _calls[call_id]

    return StatusResponse(
        call_id=call_id,
        status=call_info["status"],
        result=call_info["result"],
    )
