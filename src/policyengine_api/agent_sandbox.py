"""Modal agent using Claude API with tools auto-generated from OpenAPI spec."""

import json
import re
import time
from typing import Any, Callable

import anthropic
import modal
import requests

image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "anthropic", "requests"
)

app = modal.App("policyengine-sandbox")
anthropic_secret = modal.Secret.from_name("anthropic-api-key")

SYSTEM_PROMPT = """You are a PolicyEngine assistant that helps users understand tax and benefit policies.

You have access to the full PolicyEngine API. Key workflows:

1. **Household calculations**: POST to /household/calculate with people array, then poll GET /household/calculate/{job_id}
2. **Parameter lookup**: GET /parameters/ with search query, then GET /parameter-values/ with parameter_id
3. **Economic impact**:
   - GET /parameters/ to find parameter_id
   - POST /policies/ to create reform with parameter_values
   - GET /datasets/ to find dataset_id
   - POST /analysis/economic-impact with policy_id and dataset_id
   - Poll GET /analysis/economic-impact/{report_id} until completed

When answering questions:
1. Use the API tools to get accurate, current data
2. Show your calculations clearly
3. Be concise but thorough
4. For UK, amounts are in GBP. For US, amounts are in USD.
5. Poll async endpoints until status is "completed"

IMPORTANT: When polling async endpoints, ALWAYS use the sleep tool to wait 5-10 seconds between requests.
Do not poll in a tight loop - this wastes resources and may hit rate limits.
"""

# Sleep tool for polling delays
SLEEP_TOOL = {
    "name": "sleep",
    "description": "Wait for a specified number of seconds. Use this between polling requests to avoid hammering the API.",
    "input_schema": {
        "type": "object",
        "properties": {
            "seconds": {
                "type": "number",
                "description": "Number of seconds to sleep (1-60)",
            }
        },
        "required": ["seconds"],
    },
}


def fetch_openapi_spec(api_base_url: str) -> dict:
    """Fetch and cache OpenAPI spec."""
    resp = requests.get(f"{api_base_url}/openapi.json", timeout=30)
    resp.raise_for_status()
    return resp.json()


def resolve_ref(spec: dict, ref: str) -> dict:
    """Resolve a $ref pointer in the OpenAPI spec."""
    if not ref.startswith("#/"):
        return {}
    parts = ref[2:].split("/")
    result = spec
    for part in parts:
        result = result.get(part, {})
    return result


def schema_to_json_schema(spec: dict, schema: dict) -> dict:
    """Convert OpenAPI schema to JSON Schema for Claude tools."""
    if "$ref" in schema:
        schema = resolve_ref(spec, schema["$ref"])

    result = {}

    if "type" in schema:
        result["type"] = schema["type"]
    if "description" in schema:
        result["description"] = schema["description"]
    if "enum" in schema:
        result["enum"] = schema["enum"]
    if "default" in schema:
        result["default"] = schema["default"]
    if "format" in schema:
        # Add format info to description
        fmt = schema["format"]
        if "description" in result:
            result["description"] += f" (format: {fmt})"
        else:
            result["description"] = f"Format: {fmt}"

    # Handle anyOf (often used for Optional types)
    if "anyOf" in schema:
        non_null = [s for s in schema["anyOf"] if s.get("type") != "null"]
        if len(non_null) == 1:
            result.update(schema_to_json_schema(spec, non_null[0]))
        elif non_null:
            result.update(schema_to_json_schema(spec, non_null[0]))

    # Handle allOf
    if "allOf" in schema:
        for sub in schema["allOf"]:
            result.update(schema_to_json_schema(spec, sub))

    # Handle objects
    if schema.get("type") == "object" or "properties" in schema:
        result["type"] = "object"
        if "properties" in schema:
            result["properties"] = {}
            for prop_name, prop_schema in schema["properties"].items():
                result["properties"][prop_name] = schema_to_json_schema(
                    spec, prop_schema
                )
        if "required" in schema:
            result["required"] = schema["required"]

    # Handle arrays
    if schema.get("type") == "array" and "items" in schema:
        result["items"] = schema_to_json_schema(spec, schema["items"])

    return result


def openapi_to_claude_tools(spec: dict) -> list[dict]:
    """Convert OpenAPI spec to Claude tool definitions."""
    tools = []

    for path, methods in spec.get("paths", {}).items():
        for method, operation in methods.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue

            # Build tool name from operationId or path+method
            op_id = operation.get("operationId", f"{method}_{path}")
            # Clean up the name
            tool_name = re.sub(r"[^a-zA-Z0-9_]", "_", op_id)
            tool_name = re.sub(r"_+", "_", tool_name).strip("_")

            # Build description
            summary = operation.get("summary", "")
            description = operation.get("description", "")
            full_desc = f"{method.upper()} {path}"
            if summary:
                full_desc += f"\n\n{summary}"
            if description:
                full_desc += f"\n\n{description}"

            # Build input schema
            properties = {}
            required = []

            # Path parameters
            for param in operation.get("parameters", []):
                param_name = param.get("name")
                param_in = param.get("in")
                param_schema = param.get("schema", {})
                param_required = param.get("required", False)

                prop = schema_to_json_schema(spec, param_schema)
                prop["description"] = (
                    param.get("description", "")
                    + f" (in: {param_in})"
                )
                properties[param_name] = prop

                if param_required:
                    required.append(param_name)

            # Request body
            request_body = operation.get("requestBody", {})
            if request_body:
                content = request_body.get("content", {})
                json_content = content.get("application/json", {})
                body_schema = json_content.get("schema", {})

                if body_schema:
                    resolved = schema_to_json_schema(spec, body_schema)
                    # Flatten body properties into tool properties
                    if "properties" in resolved:
                        for prop_name, prop_schema in resolved["properties"].items():
                            properties[prop_name] = prop_schema
                        if "required" in resolved:
                            required.extend(resolved["required"])
                    else:
                        # Wrap the whole body as a "body" parameter
                        properties["body"] = resolved
                        if request_body.get("required"):
                            required.append("body")

            input_schema = {"type": "object", "properties": properties}
            if required:
                input_schema["required"] = list(set(required))

            tools.append({
                "name": tool_name,
                "description": full_desc[:1024],  # Claude has limits
                "input_schema": input_schema,
                "_meta": {
                    "path": path,
                    "method": method,
                    "parameters": operation.get("parameters", []),
                },
            })

    return tools


def execute_api_tool(
    tool: dict,
    tool_input: dict,
    api_base_url: str,
    log_fn: Callable,
) -> str:
    """Execute an API tool by making the HTTP request."""
    meta = tool.get("_meta", {})
    path = meta.get("path", "")
    method = meta.get("method", "get")
    parameters = meta.get("parameters", [])

    # Build URL with path parameters
    url = f"{api_base_url}{path}"
    query_params = {}
    headers = {"Content-Type": "application/json"}

    # Separate path, query, and body parameters
    body_data = {}
    for param in parameters:
        param_name = param.get("name")
        param_in = param.get("in")
        value = tool_input.get(param_name)

        if value is None:
            continue

        if param_in == "path":
            url = url.replace(f"{{{param_name}}}", str(value))
        elif param_in == "query":
            query_params[param_name] = value
        elif param_in == "header":
            headers[param_name] = str(value)

    # Remaining input goes to body (for POST/PUT/PATCH)
    param_names = {p.get("name") for p in parameters}
    for key, value in tool_input.items():
        if key not in param_names:
            body_data[key] = value

    try:
        log_fn(f"[API] {method.upper()} {url}")
        if query_params:
            log_fn(f"[API] Query: {json.dumps(query_params)[:200]}")
        if body_data:
            log_fn(f"[API] Body: {json.dumps(body_data)[:200]}")

        if method == "get":
            resp = requests.get(url, params=query_params, headers=headers, timeout=60)
        elif method == "post":
            resp = requests.post(
                url, params=query_params, json=body_data, headers=headers, timeout=60
            )
        elif method == "put":
            resp = requests.put(
                url, params=query_params, json=body_data, headers=headers, timeout=60
            )
        elif method == "patch":
            resp = requests.patch(
                url, params=query_params, json=body_data, headers=headers, timeout=60
            )
        elif method == "delete":
            resp = requests.delete(url, params=query_params, headers=headers, timeout=60)
        else:
            return f"Unsupported method: {method}"

        log_fn(f"[API] Response: {resp.status_code}")

        if resp.status_code >= 400:
            return f"Error {resp.status_code}: {resp.text[:500]}"

        try:
            data = resp.json()
            # For lists, summarize if too long but keep key info
            if isinstance(data, list) and len(data) > 50:
                result = json.dumps(data[:50], indent=2)
                result += f"\n... ({len(data) - 50} more items)"
            else:
                result = json.dumps(data, indent=2)
            return result
        except json.JSONDecodeError:
            return resp.text[:1000]

    except requests.RequestException as e:
        return f"Request error: {str(e)}"


def _run_agent_impl(
    question: str,
    api_base_url: str = "https://v2.api.policyengine.org",
    call_id: str = "",
    max_turns: int = 15,
) -> dict:
    """Core agent implementation."""

    def log(msg: str) -> None:
        print(msg)
        if call_id:
            try:
                requests.post(
                    f"{api_base_url}/agent/log/{call_id}",
                    json={"message": msg},
                    timeout=5,
                )
            except Exception:
                pass

    log(f"[AGENT] Starting: {question[:200]}")

    # Fetch and convert OpenAPI spec to tools
    log("[AGENT] Fetching OpenAPI spec...")
    spec = fetch_openapi_spec(api_base_url)
    tools = openapi_to_claude_tools(spec)
    log(f"[AGENT] Loaded {len(tools)} API tools")

    # Create tool lookup for execution
    tool_lookup = {t["name"]: t for t in tools}

    # Strip _meta from tools before sending to Claude (it doesn't need it)
    claude_tools = [
        {k: v for k, v in t.items() if k != "_meta"} for t in tools
    ]
    # Add the sleep tool
    claude_tools.append(SLEEP_TOOL)

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
            tools=claude_tools,
            messages=messages,
        )

        log(f"[AGENT] Stop reason: {response.stop_reason}")

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
                if block.name == "sleep":
                    # Handle sleep tool specially
                    seconds = min(max(block.input.get("seconds", 5), 1), 60)
                    log(f"[SLEEP] Waiting {seconds} seconds...")
                    time.sleep(seconds)
                    result = f"Slept for {seconds} seconds"
                else:
                    tool = tool_lookup.get(block.name)
                    if tool:
                        result = execute_api_tool(tool, block.input, api_base_url, log)
                    else:
                        result = f"Unknown tool: {block.name}"

                log(f"[TOOL_RESULT] {result[:300]}")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        messages.append({"role": "assistant", "content": assistant_content})

        if tool_results:
            messages.append({"role": "user", "content": tool_results})
        else:
            break

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
                timeout=10,
            )
        except Exception:
            pass

    return result


@app.function(image=image, secrets=[anthropic_secret], timeout=300)
def run_agent(
    question: str,
    api_base_url: str = "https://v2.api.policyengine.org",
    call_id: str = "",
    max_turns: int = 15,
) -> dict:
    """Run agentic loop to answer a policy question (Modal wrapper)."""
    return _run_agent_impl(question, api_base_url, call_id, max_turns)


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
