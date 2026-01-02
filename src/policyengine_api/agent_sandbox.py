"""Modal agent using Claude Agent SDK with MCP server connection."""

import asyncio

import modal
import requests

image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "claude-agent-sdk", "requests", "logfire[httpx]"
)

app = modal.App("policyengine-sandbox")
anthropic_secret = modal.Secret.from_name("anthropic-api-key")
logfire_secrets = modal.Secret.from_name("policyengine-logfire")


def configure_logfire(traceparent: str | None = None):
    """Configure logfire with optional trace context propagation."""
    import os

    import logfire

    token = os.environ.get("LOGFIRE_TOKEN", "")
    if not token:
        return

    logfire.configure(
        service_name="policyengine-agent",
        token=token,
        environment=os.environ.get("LOGFIRE_ENVIRONMENT", "production"),
        console=False,
    )

    if traceparent:
        from opentelemetry import context
        from opentelemetry.trace.propagation.tracecontext import (
            TraceContextTextMapPropagator,
        )

        propagator = TraceContextTextMapPropagator()
        ctx = propagator.extract(carrier={"traceparent": traceparent})
        context.attach(ctx)


SYSTEM_PROMPT = """You are a PolicyEngine assistant that helps users understand tax and benefit policies.

You have access to the PolicyEngine API via MCP tools.

## CRITICAL: Always filter by country

When searching for parameters or datasets, ALWAYS include tax_benefit_model_name:
- "policyengine-uk" for UK questions
- "policyengine-us" for US questions

Parameters and datasets from both countries are in the same database. Without the filter, you'll get mixed results.

## Key workflows

1. **Household calculations**:
   - Use household_calculate with model_name and people array
   - Poll household_calculate_status until completed

2. **Parameter lookup**:
   - Use parameters_list with search and tax_benefit_model_name filter
   - Use parameter_values_list with parameter_id and current=true

3. **Economic impact analysis**:
   - Find parameter_id with parameters_list
   - Create policy with policies_create
   - Find dataset_id with datasets_list
   - Run analysis with analysis_economic_impact
   - Get results with analysis_economic_impact_status

## Response formatting

Follow PolicyEngine's writing style:

1. **Sentence case**: Use sentence case for headings
2. **Active voice**: "The reform reduces poverty by 3.2%"
3. **Quantitative precision**: Use specific numbers
4. **Neutral tone**: Describe what policies do objectively
5. **Tables for data**: Use markdown tables for breakdowns

Example:
| Item | Amount |
|------|--------|
| Income tax | £7,486 |
| National Insurance | £2,994 |
| **Total tax** | **£10,480** |

Avoid vague words like "significantly" or "substantially" - use numbers.
"""


async def _run_agent_async(
    question: str,
    api_base_url: str,
    call_id: str,
    history: list[dict] | None = None,
    traceparent: str | None = None,
) -> dict:
    """Core async agent implementation using Claude Agent SDK."""
    from claude_agent_sdk import ClaudeAgentOptions, query

    def get_trace_headers() -> dict:
        if traceparent:
            return {"traceparent": traceparent}
        return {}

    def log(msg: str) -> None:
        print(msg)
        if call_id:
            try:
                requests.post(
                    f"{api_base_url}/agent/log/{call_id}",
                    json={"message": msg},
                    headers=get_trace_headers(),
                    timeout=5,
                )
            except Exception:
                pass

    log(f"[AGENT] Starting: {question[:200]}")
    log(f"[AGENT] Connecting to MCP server at {api_base_url}/mcp/")

    # Build conversation with history
    if history:
        # Format history as context in the prompt
        context_parts = []
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            context_parts.append(f"{role.upper()}: {content}")
        context = "\n\n".join(context_parts)
        full_prompt = f"Previous conversation:\n{context}\n\nNew question: {question}"
    else:
        full_prompt = question

    # Configure Agent SDK with MCP server
    options = ClaudeAgentOptions(
        mcp_servers={
            "policyengine": {
                "type": "sse",
                "url": f"{api_base_url}/mcp/",
            }
        },
        allowed_tools=["mcp__policyengine__*"],
        system_prompt=SYSTEM_PROMPT,
    )

    final_response = None
    turns = 0

    try:
        async for message in query(prompt=full_prompt, options=options):
            # Handle different message types
            msg_type = type(message).__name__

            if msg_type == "AssistantMessage":
                turns += 1
                for block in message.content:
                    block_type = type(block).__name__
                    if block_type == "TextBlock":
                        log(f"[ASSISTANT] {block.text[:500]}")
                        final_response = block.text
                    elif block_type == "ToolUseBlock":
                        log(f"[TOOL_USE] {block.name}: {str(block.input)[:200]}")

            elif msg_type == "ToolResultMessage":
                for result in message.content:
                    result_str = str(result)[:300]
                    log(f"[TOOL_RESULT] {result_str}")

            elif msg_type == "ResultMessage":
                log(
                    f"[AGENT] Completed - Cost: ${message.cost:.4f}, Duration: {message.duration:.1f}s"
                )

    except Exception as e:
        log(f"[AGENT] Error: {str(e)}")
        return {
            "status": "failed",
            "error": str(e),
            "turns": turns,
        }

    log(f"[AGENT] Completed in {turns} turns")

    result = {
        "status": "completed",
        "result": final_response,
        "turns": turns,
    }

    if call_id:
        try:
            requests.post(
                f"{api_base_url}/agent/complete/{call_id}",
                json=result,
                headers=get_trace_headers(),
                timeout=10,
            )
        except Exception:
            pass

    return result


def _run_agent_impl(
    question: str,
    api_base_url: str = "https://v2.api.policyengine.org",
    call_id: str = "",
    history: list[dict] | None = None,
    max_turns: int = 30,
    traceparent: str | None = None,
) -> dict:
    """Synchronous wrapper for the async agent implementation."""
    return asyncio.run(
        _run_agent_async(question, api_base_url, call_id, history, traceparent)
    )


@app.function(image=image, secrets=[anthropic_secret, logfire_secrets], timeout=600)
def run_agent(
    question: str,
    api_base_url: str = "https://v2.api.policyengine.org",
    call_id: str = "",
    history: list[dict] | None = None,
    max_turns: int = 30,
    traceparent: str | None = None,
) -> dict:
    """Run agentic loop to answer a policy question (Modal wrapper)."""
    import logfire

    configure_logfire(traceparent)

    try:
        with logfire.span("run_agent", call_id=call_id, question=question[:200]):
            result = _run_agent_impl(
                question,
                api_base_url,
                call_id,
                history=history,
                max_turns=max_turns,
                traceparent=traceparent,
            )
    finally:
        logfire.force_flush()

    return result


if __name__ == "__main__":
    import sys

    question = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "What is the UK personal allowance amount?"
    )
    print(f"Question: {question}\n")

    result = _run_agent_impl(question)
    print(f"\nResult: {result}")
