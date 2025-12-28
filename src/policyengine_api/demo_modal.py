"""Modal functions for the demo agent.

This module provides Modal Sandbox-based execution of the policy agent,
allowing isolated, scalable execution of AI-powered policy analysis.
"""

import modal

# Agent image with Claude SDK and HTTP client
agent_image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "anthropic>=0.40.0",
    "httpx>=0.27.0",
)

app = modal.App("policyengine-demo")

# Secrets for Claude API
claude_secret = modal.Secret.from_name("anthropic-api-key")


@app.function(
    image=agent_image,
    secrets=[claude_secret],
    timeout=300,
    memory=512,
)
def run_policy_agent(question: str, api_base_url: str) -> dict:
    """Run the policy agent in a Modal container.

    Args:
        question: Natural language policy question
        api_base_url: Base URL of the PolicyEngine API

    Returns:
        Dict with 'report' (markdown) and 'status' fields
    """
    import json
    import time

    import anthropic
    import httpx

    # Define tools inline to avoid import issues
    tools = [
        {
            "name": "search_parameters",
            "description": "Search for tax-benefit parameters by name or description. Use this to find parameter IDs for creating policy reforms.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["query"],
            },
        },
        {
            "name": "get_parameter",
            "description": "Get detailed information about a specific parameter.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "parameter_id": {
                        "type": "string",
                        "description": "UUID of the parameter",
                    },
                },
                "required": ["parameter_id"],
            },
        },
        {
            "name": "list_datasets",
            "description": "List available population datasets for economic impact analysis.",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "create_policy",
            "description": "Create a policy reform with parameter changes.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "parameter_values": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "parameter_id": {"type": "string"},
                                "value_json": {},
                                "start_date": {"type": "string"},
                            },
                            "required": ["parameter_id", "value_json", "start_date"],
                        },
                    },
                },
                "required": ["name", "parameter_values"],
            },
        },
        {
            "name": "run_economic_impact",
            "description": "Run economy-wide impact analysis. Returns report_id to poll.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "country": {"type": "string", "enum": ["uk", "us"]},
                    "dataset_id": {"type": "string"},
                    "policy_id": {"type": "string"},
                },
                "required": ["country", "dataset_id", "policy_id"],
            },
        },
        {
            "name": "get_economic_impact_status",
            "description": "Check status of economic impact analysis. Poll until 'completed'.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "report_id": {"type": "string"},
                },
                "required": ["report_id"],
            },
        },
        {
            "name": "calculate_household",
            "description": "Calculate taxes/benefits for a household.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "country": {"type": "string", "enum": ["uk", "us"]},
                    "people": {"type": "array", "items": {"type": "object"}},
                    "year": {"type": "integer"},
                    "policy_id": {"type": "string"},
                },
                "required": ["country", "people"],
            },
        },
        {
            "name": "get_household_status",
            "description": "Check status of household calculation.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                },
                "required": ["job_id"],
            },
        },
    ]

    # HTTP client for PolicyEngine API
    client = httpx.Client(timeout=60.0, base_url=api_base_url)

    def call_api(tool_name: str, tool_input: dict) -> str:
        """Execute API call for a tool."""
        try:
            if tool_name == "search_parameters":
                resp = client.get(
                    "/parameters/",
                    params={
                        "search": tool_input["query"],
                        "limit": tool_input.get("limit", 20),
                    },
                )
            elif tool_name == "get_parameter":
                resp = client.get(f"/parameters/{tool_input['parameter_id']}")
            elif tool_name == "list_datasets":
                resp = client.get("/datasets/")
            elif tool_name == "create_policy":
                resp = client.post(
                    "/policies/",
                    json={
                        "name": tool_input["name"],
                        "description": tool_input.get("description"),
                        "parameter_values": tool_input["parameter_values"],
                    },
                )
            elif tool_name == "run_economic_impact":
                resp = client.post(
                    "/analysis/economic-impact",
                    json={
                        "tax_benefit_model_name": f"policyengine_{tool_input['country']}",
                        "dataset_id": tool_input["dataset_id"],
                        "policy_id": tool_input["policy_id"],
                    },
                )
            elif tool_name == "get_economic_impact_status":
                resp = client.get(
                    f"/analysis/economic-impact/{tool_input['report_id']}"
                )
            elif tool_name == "calculate_household":
                body = {
                    "tax_benefit_model_name": f"policyengine_{tool_input['country']}",
                    "people": tool_input["people"],
                }
                if tool_input.get("year"):
                    body["year"] = tool_input["year"]
                if tool_input.get("policy_id"):
                    body["policy_id"] = tool_input["policy_id"]
                resp = client.post("/household/calculate", json=body)
            elif tool_name == "get_household_status":
                resp = client.get(f"/household/calculate/{tool_input['job_id']}")
            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})

            resp.raise_for_status()
            return json.dumps(resp.json(), indent=2)
        except httpx.HTTPStatusError as e:
            return json.dumps(
                {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
            )
        except Exception as e:
            return json.dumps({"error": str(e)})

    # Claude client
    anthropic_client = anthropic.Anthropic()

    system_prompt = """You are a policy analyst assistant using the PolicyEngine API to answer tax/benefit policy questions.

Workflow:
1. Search for relevant parameters
2. Create a policy reform
3. Run economic impact analysis (poll until completed)
4. Summarise findings

For UK questions use country="uk", for US use country="us".
When polling, wait between requests.

Format your final answer as markdown with:
- Headline finding (cost/revenue, e.g. "£X billion per year")
- Distributional impacts (who wins/loses by income decile)
- Key program effects

Be concise. Use British English for UK questions."""

    messages = [{"role": "user", "content": question}]

    # Agent loop
    for _ in range(25):
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    return {"status": "completed", "report": block.text}
            return {"status": "completed", "report": "No response generated."}

        # Process tool calls
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(
                    f"[Agent] Calling {block.name}: {json.dumps(block.input)[:100]}..."
                )
                result = call_api(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )
                # Delay for polling
                if block.name in ("get_economic_impact_status", "get_household_status"):
                    time.sleep(3)

        if not tool_results:
            for block in response.content:
                if hasattr(block, "text"):
                    return {"status": "completed", "report": block.text}
            return {"status": "error", "report": "Agent stopped unexpectedly."}

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    return {"status": "error", "report": "Agent exceeded maximum iterations."}


# Alternative: Sandbox-based execution for full isolation
@app.function(image=agent_image, secrets=[claude_secret], timeout=300)
def run_policy_agent_sandbox(question: str, api_base_url: str) -> dict:
    """Run agent in a fully isolated Modal Sandbox.

    This provides extra isolation but has slightly higher latency.
    """

    # Write the agent script to a temp file and execute in sandbox
    # For now, just use the direct function above
    return run_policy_agent.local(question, api_base_url)
