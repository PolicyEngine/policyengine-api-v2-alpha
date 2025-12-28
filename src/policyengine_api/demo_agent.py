"""Demo agent that uses Claude to answer policy questions via the PolicyEngine API.

This module provides a Modal Sandbox-based agent that:
1. Takes a natural language policy question
2. Uses Claude with tool calling to interact with the PolicyEngine API
3. Runs simulations and analyses as needed
4. Returns a markdown report with findings
"""

import json
import os
import time
from typing import Any

import anthropic
import httpx

# PolicyEngine API tools for Claude
TOOLS = [
    {
        "name": "search_parameters",
        "description": "Search for tax-benefit parameters by name or description. Use this to find parameter IDs for creating policy reforms. For example, search 'basic rate' to find income tax basic rate parameters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for parameter name/description",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default 20)",
                    "default": 20,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_parameter",
        "description": "Get detailed information about a specific parameter including its current values.",
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
        "description": "List available population datasets for economic impact analysis. Returns dataset IDs needed for economy-wide simulations.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "create_policy",
        "description": "Create a policy reform with parameter changes. Returns a policy ID for use in simulations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the policy reform",
                },
                "description": {
                    "type": "string",
                    "description": "Description of what the policy does",
                },
                "parameter_values": {
                    "type": "array",
                    "description": "List of parameter changes",
                    "items": {
                        "type": "object",
                        "properties": {
                            "parameter_id": {
                                "type": "string",
                                "description": "UUID of parameter to change",
                            },
                            "value_json": {
                                "description": "New value for the parameter",
                            },
                            "start_date": {
                                "type": "string",
                                "description": "Start date (ISO format), e.g. 2024-01-01T00:00:00Z",
                            },
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
        "description": "Run economy-wide impact analysis comparing baseline (current law) vs a policy reform. Returns decile impacts and program statistics. This is async - returns a report_id to poll.",
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {
                    "type": "string",
                    "enum": ["uk", "us"],
                    "description": "Which country model to use",
                },
                "dataset_id": {
                    "type": "string",
                    "description": "UUID of the dataset to use (from list_datasets)",
                },
                "policy_id": {
                    "type": "string",
                    "description": "UUID of the policy reform (from create_policy)",
                },
            },
            "required": ["country", "dataset_id", "policy_id"],
        },
    },
    {
        "name": "get_economic_impact_status",
        "description": "Check status of an economic impact analysis. Poll until status is 'completed' to get results.",
        "input_schema": {
            "type": "object",
            "properties": {
                "report_id": {
                    "type": "string",
                    "description": "UUID of the report (from run_economic_impact)",
                },
            },
            "required": ["report_id"],
        },
    },
    {
        "name": "calculate_household",
        "description": "Calculate taxes and benefits for a specific household. Useful for illustrative examples.",
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {
                    "type": "string",
                    "enum": ["uk", "us"],
                    "description": "Which country model to use",
                },
                "people": {
                    "type": "array",
                    "description": "List of people with their characteristics",
                    "items": {
                        "type": "object",
                        "properties": {
                            "age": {"type": "integer"},
                            "employment_income": {"type": "number"},
                        },
                    },
                },
                "year": {
                    "type": "integer",
                    "description": "Simulation year (default 2024 for US, 2026 for UK)",
                },
                "policy_id": {
                    "type": "string",
                    "description": "Optional policy reform ID",
                },
            },
            "required": ["country", "people"],
        },
    },
    {
        "name": "get_household_status",
        "description": "Check status of a household calculation. Poll until status is 'completed'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_id": {
                    "type": "string",
                    "description": "UUID of the job (from calculate_household)",
                },
            },
            "required": ["job_id"],
        },
    },
]


class PolicyEngineClient:
    """HTTP client for the PolicyEngine API."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=60.0)

    def search_parameters(self, query: str, limit: int = 20) -> dict:
        resp = self.client.get(
            f"{self.base_url}/parameters/",
            params={"search": query, "limit": limit},
        )
        resp.raise_for_status()
        return resp.json()

    def get_parameter(self, parameter_id: str) -> dict:
        resp = self.client.get(f"{self.base_url}/parameters/{parameter_id}")
        resp.raise_for_status()
        return resp.json()

    def list_datasets(self) -> dict:
        resp = self.client.get(f"{self.base_url}/datasets/")
        resp.raise_for_status()
        return resp.json()

    def create_policy(
        self, name: str, parameter_values: list, description: str | None = None
    ) -> dict:
        resp = self.client.post(
            f"{self.base_url}/policies/",
            json={
                "name": name,
                "description": description,
                "parameter_values": parameter_values,
            },
        )
        resp.raise_for_status()
        return resp.json()

    def run_economic_impact(
        self, country: str, dataset_id: str, policy_id: str
    ) -> dict:
        model_name = f"policyengine_{country}"
        resp = self.client.post(
            f"{self.base_url}/analysis/economic-impact",
            json={
                "tax_benefit_model_name": model_name,
                "dataset_id": dataset_id,
                "policy_id": policy_id,
            },
        )
        resp.raise_for_status()
        return resp.json()

    def get_economic_impact_status(self, report_id: str) -> dict:
        resp = self.client.get(f"{self.base_url}/analysis/economic-impact/{report_id}")
        resp.raise_for_status()
        return resp.json()

    def calculate_household(
        self,
        country: str,
        people: list,
        year: int | None = None,
        policy_id: str | None = None,
    ) -> dict:
        model_name = f"policyengine_{country}"
        body: dict[str, Any] = {
            "tax_benefit_model_name": model_name,
            "people": people,
        }
        if year:
            body["year"] = year
        if policy_id:
            body["policy_id"] = policy_id

        resp = self.client.post(
            f"{self.base_url}/household/calculate",
            json=body,
        )
        resp.raise_for_status()
        return resp.json()

    def get_household_status(self, job_id: str) -> dict:
        resp = self.client.get(f"{self.base_url}/household/calculate/{job_id}")
        resp.raise_for_status()
        return resp.json()


def execute_tool(client: PolicyEngineClient, tool_name: str, tool_input: dict) -> str:
    """Execute a tool call and return the result as a string."""
    try:
        if tool_name == "search_parameters":
            result = client.search_parameters(
                tool_input["query"], tool_input.get("limit", 20)
            )
        elif tool_name == "get_parameter":
            result = client.get_parameter(tool_input["parameter_id"])
        elif tool_name == "list_datasets":
            result = client.list_datasets()
        elif tool_name == "create_policy":
            result = client.create_policy(
                tool_input["name"],
                tool_input["parameter_values"],
                tool_input.get("description"),
            )
        elif tool_name == "run_economic_impact":
            result = client.run_economic_impact(
                tool_input["country"],
                tool_input["dataset_id"],
                tool_input["policy_id"],
            )
        elif tool_name == "get_economic_impact_status":
            result = client.get_economic_impact_status(tool_input["report_id"])
        elif tool_name == "calculate_household":
            result = client.calculate_household(
                tool_input["country"],
                tool_input["people"],
                tool_input.get("year"),
                tool_input.get("policy_id"),
            )
        elif tool_name == "get_household_status":
            result = client.get_household_status(tool_input["job_id"])
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        return json.dumps(result, indent=2)
    except httpx.HTTPStatusError as e:
        return json.dumps(
            {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


def run_agent(question: str, api_base_url: str) -> str:
    """Run the policy agent to answer a question.

    Args:
        question: Natural language policy question
        api_base_url: Base URL of the PolicyEngine API

    Returns:
        Markdown report answering the question
    """
    anthropic_client = anthropic.Anthropic()
    pe_client = PolicyEngineClient(api_base_url)

    system_prompt = """You are a policy analyst assistant that uses the PolicyEngine API to answer questions about tax and benefit policy.

When answering questions:
1. First search for relevant parameters to understand what can be changed
2. Create a policy reform with the requested changes
3. Run an economic impact analysis to see the effects
4. Summarise findings in a clear, concise report

For UK questions, use country="uk". For US questions, use country="us".

When polling for results (economic impact or household calculations), wait a few seconds between polls.

Format your final answer as a markdown report with:
- A headline finding (e.g. "This would cost £X billion per year")
- Key distributional impacts (who wins/loses)
- Relevant program-level effects

Be concise and focus on the numbers. Use British English for UK questions."""

    messages = [{"role": "user", "content": question}]

    # Agent loop
    max_iterations = 20
    for _ in range(max_iterations):
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        # Check if we're done
        if response.stop_reason == "end_turn":
            # Extract final text response
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return "No response generated."

        # Process tool calls
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"Calling tool: {block.name}")
                result = execute_tool(pe_client, block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )

                # Add small delay for polling operations
                if block.name in (
                    "get_economic_impact_status",
                    "get_household_status",
                ):
                    time.sleep(2)

        if not tool_results:
            # No tool calls and not end_turn - extract any text
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return "Agent stopped unexpectedly."

        # Add assistant message and tool results
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    return "Agent exceeded maximum iterations."


if __name__ == "__main__":
    # Test locally
    import sys

    question = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "How much would it cost to set the UK basic income tax rate to 19p?"
    )
    api_url = os.environ.get("POLICYENGINE_API_URL", "https://v2.api.policyengine.org")

    print(f"Question: {question}\n")
    print(f"API: {api_url}\n")
    print("=" * 60)

    result = run_agent(question, api_url)
    print(result)
