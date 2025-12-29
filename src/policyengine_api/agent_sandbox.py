"""Modal agent using Claude API directly with PolicyEngine tools."""

import json
import os

import anthropic
import modal
import requests

# Simple image with just what we need
image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "anthropic", "requests"
)

app = modal.App("policyengine-sandbox")
anthropic_secret = modal.Secret.from_name("anthropic-api-key")

# Core PolicyEngine tools - derived from our API
TOOLS = [
    {
        "name": "calculate_household",
        "description": "Calculate taxes and benefits for a household. Returns detailed breakdown of income tax, NI, benefits, and net income.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tax_benefit_model_name": {
                    "type": "string",
                    "enum": ["policyengine_uk", "policyengine_us"],
                    "description": "Which country model to use",
                },
                "people": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "List of people with flat values, e.g., [{'age': 35, 'employment_income': 35000}]",
                },
                "household": {
                    "type": "object",
                    "description": "Household-level attributes (usually empty for UK, may include state_fips for US)",
                    "default": {},
                },
                "year": {
                    "type": "integer",
                    "description": "Simulation year (2026 for UK, 2024 for US)",
                    "default": 2026,
                },
            },
            "required": ["tax_benefit_model_name", "people"],
        },
    },
    {
        "name": "get_parameter",
        "description": "Get current value of a policy parameter (e.g., income tax rates, benefit amounts, thresholds)",
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {"type": "string", "enum": ["uk", "us"]},
                "parameter": {
                    "type": "string",
                    "description": "Parameter path, e.g., 'gov.hmrc.income_tax.rates.uk'",
                },
            },
            "required": ["country", "parameter"],
        },
    },
    {
        "name": "search_parameters",
        "description": "Search for policy parameters by keyword",
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {"type": "string", "enum": ["uk", "us"]},
                "query": {"type": "string", "description": "Search term"},
            },
            "required": ["country", "query"],
        },
    },
]

SYSTEM_PROMPT = """You are a PolicyEngine assistant that helps users understand tax and benefit policies.

You have access to tools to:
- Calculate taxes and benefits for specific households
- Look up policy parameters (rates, thresholds, amounts)
- Search for parameters by keyword

When answering questions:
1. Use the tools to get accurate, current data
2. Show your calculations clearly
3. Be concise but thorough
4. For UK, amounts are in GBP. For US, amounts are in USD.

Example calculate_household call:
{
  "tax_benefit_model_name": "policyengine_uk",
  "people": [{"age": 35, "employment_income": 50000}],
  "year": 2026
}
"""


def execute_tool(
    tool_name: str, tool_input: dict, api_base_url: str, log_fn
) -> str:
    """Execute a tool and return the result as a string."""
    import time

    try:
        if tool_name == "calculate_household":
            # Call our household calculation endpoint
            resp = requests.post(
                f"{api_base_url}/household/calculate",
                json={
                    "tax_benefit_model_name": tool_input.get("tax_benefit_model_name", "policyengine_uk"),
                    "people": tool_input.get("people", []),
                    "household": tool_input.get("household", {}),
                    "year": tool_input.get("year"),
                },
                timeout=60,
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                job_id = data.get("job_id")
                if job_id:
                    log_fn(f"[TOOL] Job {job_id} started, polling...")
                    for _ in range(30):
                        time.sleep(2)
                        status_resp = requests.get(
                            f"{api_base_url}/household/calculate/{job_id}",
                            timeout=30,
                        )
                        if status_resp.status_code == 200:
                            status_data = status_resp.json()
                            if status_data.get("status") == "completed":
                                result = status_data.get("result", {})
                                # Extract key values for readability
                                summary = {}
                                if result.get("person"):
                                    for person in result["person"]:
                                        for k, v in person.items():
                                            if isinstance(v, (int, float)) and abs(v) > 0.01:
                                                summary[k] = round(v, 2)
                                return json.dumps(summary, indent=2)
                            elif status_data.get("status") == "failed":
                                return f"Calculation failed: {status_data.get('error_message', 'Unknown error')}"
                    return "Calculation timed out"
                return json.dumps(data, indent=2)
            return f"Error: {resp.status_code} - {resp.text[:500]}"

        elif tool_name == "get_parameter":
            country = tool_input.get("country", "uk")
            param = tool_input.get("parameter", "")
            # Normalize: replace spaces with underscores for API search
            search_term = param.replace(" ", "_").lower()
            resp = requests.get(
                f"{api_base_url}/parameters/",  # Note trailing slash
                params={"search": search_term, "limit": 5},
                timeout=30,
            )
            if resp.status_code == 200:
                params = resp.json()
                if not params:
                    return "No parameters found matching that query"
                # Get values for first matching parameter
                results = []
                for p in params[:3]:
                    param_id = p.get("id")
                    if param_id:
                        val_resp = requests.get(
                            f"{api_base_url}/parameter-values/",
                            params={"parameter_id": param_id, "limit": 1},
                            timeout=10,
                        )
                        value = None
                        if val_resp.status_code == 200:
                            vals = val_resp.json()
                            if vals:
                                value = vals[0].get("value_json")
                        results.append({
                            "name": p.get("name"),
                            "label": p.get("label"),
                            "value": value,
                            "unit": p.get("unit"),
                        })
                return json.dumps(results, indent=2)
            return f"Error: {resp.status_code}"

        elif tool_name == "search_parameters":
            country = tool_input.get("country", "uk")
            query = tool_input.get("query", "")
            # Normalize: replace spaces with underscores for API search
            search_term = query.replace(" ", "_").lower()
            resp = requests.get(
                f"{api_base_url}/parameters/",  # Note trailing slash
                params={"search": search_term, "limit": 10},
                timeout=30,
            )
            if resp.status_code == 200:
                params = resp.json()
                if not params:
                    return "No parameters found matching that query"
                simplified = [{"name": p.get("name"), "label": p.get("label"), "unit": p.get("unit")} for p in params[:10]]
                return json.dumps(simplified, indent=2)
            return f"Error: {resp.status_code}"

        else:
            return f"Unknown tool: {tool_name}"

    except Exception as e:
        return f"Tool error: {str(e)}"


def post_log(api_base_url: str, call_id: str, message: str) -> None:
    """POST a log entry to the API."""
    try:
        requests.post(
            f"{api_base_url}/agent/log/{call_id}",
            json={"message": message},
            timeout=5,
        )
    except Exception:
        pass


def post_complete(api_base_url: str, call_id: str, result: dict) -> None:
    """POST completion status to the API."""
    try:
        requests.post(
            f"{api_base_url}/agent/complete/{call_id}",
            json=result,
            timeout=10,
        )
    except Exception:
        pass


@app.function(image=image, secrets=[anthropic_secret], timeout=300)
def run_agent(
    question: str,
    api_base_url: str = "https://v2.api.policyengine.org",
    call_id: str = "",
    max_turns: int = 10,
) -> dict:
    """Run agentic loop to answer a policy question."""

    def log(msg: str) -> None:
        print(msg)
        if call_id:
            post_log(api_base_url, call_id, msg)

    log(f"[AGENT] Starting: {question[:200]}")

    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": question}]

    final_response = None
    turns = 0

    while turns < max_turns:
        turns += 1
        log(f"[AGENT] Turn {turns}")

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        log(f"[AGENT] Stop reason: {response.stop_reason}")

        # Collect assistant response
        assistant_content = []
        tool_results = []

        for block in response.content:
            if block.type == "text":
                log(f"[ASSISTANT] {block.text[:500]}")
                assistant_content.append(block)
                final_response = block.text
            elif block.type == "tool_use":
                log(f"[TOOL_USE] {block.name}: {json.dumps(block.input)[:200]}")
                assistant_content.append(block)

                # Execute tool
                result = execute_tool(block.name, block.input, api_base_url, log)
                log(f"[TOOL_RESULT] {result[:300]}")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        # Add assistant message
        messages.append({"role": "assistant", "content": assistant_content})

        # If there were tool uses, add results and continue
        if tool_results:
            messages.append({"role": "user", "content": tool_results})
        else:
            # No tool use, we're done
            break

    log(f"[AGENT] Completed in {turns} turns")

    result = {
        "status": "completed",
        "result": final_response,
        "turns": turns,
    }

    if call_id:
        post_complete(api_base_url, call_id, result)

    return result


if __name__ == "__main__":
    import sys

    question = sys.argv[1] if len(sys.argv) > 1 else "What is the UK basic rate of income tax?"
    print(f"Question: {question}\n")

    with modal.enable_local():
        result = run_agent.local(question)
        print(f"\nResult: {result}")
