"""Demo endpoint for AI-powered policy analysis.

This endpoint lets users ask natural language questions about tax/benefit policy
and get AI-generated reports using the PolicyEngine API.
"""

import os
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/demo", tags=["demo"])


class AskRequest(BaseModel):
    """Request to ask a policy question."""

    question: str
    country: str = "uk"  # Default to UK


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


# In-memory job storage (use Redis/DB in production)
_jobs: dict[str, dict] = {}


def _run_agent_task(job_id: str, question: str, api_base_url: str) -> None:
    """Background task to run the agent via Modal."""
    import modal

    try:
        _jobs[job_id]["status"] = "running"

        # Call the Modal function
        run_policy_agent = modal.Function.lookup(
            "policyengine-demo", "run_policy_agent"
        )
        result = run_policy_agent.remote(question, api_base_url)

        _jobs[job_id]["status"] = result.get("status", "completed")
        _jobs[job_id]["report"] = result.get("report")

    except Exception as e:
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(e)


@router.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    background_tasks: BackgroundTasks,
) -> AskResponse:
    """Ask a natural language policy question.

    Spawns an AI agent that uses the PolicyEngine API to:
    1. Find relevant parameters
    2. Create policy reforms
    3. Run economic impact analysis
    4. Generate a markdown report

    Poll GET /demo/status/{job_id} for results.

    Example questions:
    - "How much would it cost to set the UK basic income tax rate to 19p?"
    - "What would happen if we doubled child benefit?"
    - "How would a £15,000 personal allowance affect different income groups?"
    """
    job_id = str(uuid4())

    # Store job
    _jobs[job_id] = {
        "status": "pending",
        "question": request.question,
        "report": None,
        "error": None,
    }

    # Get API base URL (use production by default)
    api_base_url = os.environ.get(
        "POLICYENGINE_API_URL", "https://v2.api.policyengine.org"
    )

    # Start background task
    background_tasks.add_task(_run_agent_task, job_id, request.question, api_base_url)

    return AskResponse(job_id=job_id, status="pending")


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """Get the status of a demo job.

    Poll this endpoint until status is 'completed' or 'failed'.
    """
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = _jobs[job_id]
    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        report=job.get("report"),
        error=job.get("error"),
    )
