"""Modal Sandbox for running Claude Code with PolicyEngine MCP server.

This runs the actual Claude Code CLI in an isolated sandbox, connected
to the PolicyEngine API via MCP. Outputs are streamed back in real-time.
"""

import json

import modal
from modal.stream_type import StreamType

# Sandbox image with Bun and Claude Code CLI (v3 - with stdbuf for unbuffered output)
sandbox_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("curl", "git", "unzip", "coreutils")  # coreutils provides stdbuf
    .pip_install("logfire")
    .run_commands(
        # Install Bun
        "curl -fsSL https://bun.sh/install | bash",
        # Add bun to PATH, create node symlink (Claude CLI needs it), install Claude Code
        "export BUN_INSTALL=/root/.bun && export PATH=$BUN_INSTALL/bin:$PATH && "
        "ln -s $BUN_INSTALL/bin/bun /usr/local/bin/node && "
        "bun install -g @anthropic-ai/claude-code",
        # Pre-accept ToS and configure for non-interactive use (v2)
        "mkdir -p /root/.claude && "
        'echo \'{"hasCompletedOnboarding": true, "hasAcknowledgedCostThreshold": true}\' '
        "> /root/.claude/settings.json && cat /root/.claude/settings.json",
    )
    .env(
        {
            "BUN_INSTALL": "/root/.bun",
            "PATH": "/root/.bun/bin:/usr/local/bin:/usr/bin:/bin",
            "CLAUDE_CODE_SKIP_ONBOARDING": "1",  # Cache bust + extra safety
        }
    )
)

app = modal.App("policyengine-sandbox")

# Secrets
anthropic_secret = modal.Secret.from_name("anthropic-api-key")
logfire_secret = modal.Secret.from_name("logfire-token")


async def run_claude_code_in_sandbox_async(
    question: str,
    api_base_url: str = "https://v2.api.policyengine.org",
) -> tuple[modal.Sandbox, any]:
    """Create a sandbox running Claude Code with MCP server configured.

    Returns the sandbox and process handle for streaming output.
    Uses Modal's async API for proper streaming support.
    """
    import logfire

    logfire.info(
        "run_claude_code_in_sandbox: starting",
        question=question[:100],
        api_base_url=api_base_url,
    )

    # MCP config for Claude Code (type: sse for HTTP SSE transport)
    mcp_config = {
        "mcpServers": {"policyengine": {"type": "sse", "url": f"{api_base_url}/mcp"}}
    }
    mcp_config_json = json.dumps(mcp_config)

    # Get reference to deployed app (required when calling from outside Modal)
    logfire.info("run_claude_code_in_sandbox: looking up Modal app")
    sandbox_app = modal.App.lookup("policyengine-sandbox", create_if_missing=True)
    logfire.info("run_claude_code_in_sandbox: Modal app found")

    logfire.info("run_claude_code_in_sandbox: creating sandbox")
    sb = await modal.Sandbox.create.aio(
        app=sandbox_app,
        image=sandbox_image,
        secrets=[anthropic_secret, logfire_secret],
        timeout=600,
        workdir="/tmp",
    )
    logfire.info("run_claude_code_in_sandbox: sandbox created")

    # Escape the question and config for shell
    escaped_question = question.replace("'", "'\"'\"'")
    escaped_mcp_config = mcp_config_json.replace("'", "'\"'\"'")
    # CRITICAL: < /dev/null closes stdin (otherwise Claude hangs waiting for input)
    # 2>&1 merges stderr into stdout for unified streaming
    # stdbuf -oL forces line-buffered stdout to prevent libc buffering
    cmd = (
        f"stdbuf -oL claude -p '{escaped_question}' "
        f"--mcp-config '{escaped_mcp_config}' "
        "--output-format stream-json --verbose --max-turns 10 "
        "--allowedTools 'mcp__policyengine__*,Bash,Read,Grep,Glob,Write,Edit' "
        "< /dev/null 2>&1"
    )
    logfire.info(
        "run_claude_code_in_sandbox: executing",
        cmd=cmd[:500],
        question_len=len(question),
        escaped_question_len=len(escaped_question),
    )
    # Use async exec for proper streaming
    # stdout=StreamType.PIPE allows us to consume the stream (default but explicit)
    process = await sb.exec.aio(
        "sh",
        "-c",
        cmd,
        text=True,
        bufsize=1,
        stdout=StreamType.PIPE,
    )
    logfire.info("run_claude_code_in_sandbox: claude CLI process started, returning.")

    return sb, process


def _get_api_system_prompt(api_base_url: str) -> str:
    """Generate system prompt with PolicyEngine API documentation."""
    return f"""You are a PolicyEngine policy analyst. Answer questions about tax and benefit policy using the PolicyEngine API at {api_base_url}.

Use curl to call the API. All responses are JSON.

## WORKFLOW 1: Household calculation (single family taxes/benefits)

Step 1: Calculate household taxes/benefits
```bash
curl -X POST {api_base_url}/household/calculate \\
  -H "Content-Type: application/json" \\
  -d '{{
    "tax_benefit_model_name": "policyengine_uk",
    "people": [{{"employment_income": 50000, "age": 35}}],
    "household": {{}},
    "year": 2026
  }}'
```
Returns: {{"job_id": "uuid", "status": "pending"}}

Step 2: Poll until status="completed"
```bash
curl {api_base_url}/household/calculate/{{job_id}}
```
Returns: {{"status": "completed", "result": {{"person": [...], "household": {{...}}}}}}

### UK household example:
```json
{{
  "tax_benefit_model_name": "policyengine_uk",
  "people": [{{"employment_income": 50000, "age": 35}}],
  "benunit": {{}},
  "household": {{}},
  "year": 2026
}}
```

### US household example:
```json
{{
  "tax_benefit_model_name": "policyengine_us",
  "people": [{{"employment_income": 70000, "age": 40}}],
  "tax_unit": {{"state_code": "CA"}},
  "household": {{"state_fips": 6}},
  "year": 2024
}}
```

IMPORTANT: Use FLAT values like {{"employment_income": 50000}}, NOT time-period format like {{"employment_income": {{"2024": 50000}}}}.

## WORKFLOW 2: Economic impact analysis (budgetary/distributional effects)

This workflow analyses how a policy reform affects the whole economy.

Step 1: Search for the parameter you want to change
```bash
curl "{api_base_url}/parameters?search=basic_rate"
```
Look for the parameter with a name like "gov.hmrc.income_tax.rates.uk[0].rate" and note its "id" field.

Step 2: Get dataset ID for the country
```bash
curl {api_base_url}/datasets
```
For UK, find the "enhanced_frs" dataset. For US, find "enhanced_cps". Note the "id" field.

Step 3: Create a policy reform
```bash
curl -X POST {api_base_url}/policies \\
  -H "Content-Type: application/json" \\
  -d '{{
    "name": "Lower basic rate to 16p",
    "description": "Reduce UK basic income tax rate from 20p to 16p",
    "parameter_values": [
      {{
        "parameter_id": "<uuid-from-step-1>",
        "value_json": 0.16,
        "start_date": "2026-01-01T00:00:00Z",
        "end_date": null
      }}
    ]
  }}'
```
Returns: {{"id": "policy-uuid", ...}}

Step 4: Run economic impact analysis
```bash
curl -X POST {api_base_url}/analysis/economic-impact \\
  -H "Content-Type: application/json" \\
  -d '{{
    "tax_benefit_model_name": "policyengine_uk",
    "dataset_id": "<dataset-uuid-from-step-2>",
    "policy_id": "<policy-uuid-from-step-3>"
  }}'
```
Returns: {{"report_id": "uuid", "status": "pending", ...}}

Step 5: Poll until status="completed"
```bash
curl {api_base_url}/analysis/economic-impact/{{report_id}}
```
Returns: {{"status": "completed", "decile_impacts": [...], "program_statistics": [...]}}

## WORKFLOW 3: Household impact comparison (baseline vs reform)

Compare how a specific household is affected by a policy reform.

Step 1: Create a policy reform (same as Workflow 2, Step 3)

Step 2: Run household impact comparison
```bash
curl -X POST {api_base_url}/household/impact \\
  -H "Content-Type: application/json" \\
  -d '{{
    "tax_benefit_model_name": "policyengine_uk",
    "people": [{{"employment_income": 50000, "age": 35}}],
    "household": {{}},
    "year": 2026,
    "policy_id": "<policy-uuid>"
  }}'
```

Step 3: Poll until status="completed"
```bash
curl {api_base_url}/household/impact/{{job_id}}
```
Returns: {{"baseline_result": {{...}}, "reform_result": {{...}}, "impact": {{...}}}}

## API REFERENCE

### Parameters (policy levers that can be changed)
- GET /parameters?search=<term> - search by name/label/description
- GET /parameters/{{id}} - get parameter details

Common UK parameters:
- "gov.hmrc.income_tax.rates.uk[0].rate" - basic rate (currently 0.20)
- "gov.hmrc.income_tax.rates.uk[1].rate" - higher rate (currently 0.40)
- "gov.hmrc.income_tax.allowances.personal_allowance.amount" - personal allowance
- "gov.dwp.child_benefit.weekly.eldest" - child benefit eldest child weekly amount
- "gov.dwp.universal_credit.elements.standard_allowance.single_young" - UC standard allowance

Common US parameters:
- "gov.irs.income.bracket.rates" - federal income tax rates
- "gov.irs.credits.ctc.amount.base" - child tax credit amount

### Variables (computed values like income_tax, net_income)
- GET /variables?search=<term> - search variables
- GET /variables/{{id}} - get variable details

Common variables: income_tax, national_insurance, universal_credit, child_benefit, net_income, household_net_income

### Datasets (population microdata for economic analysis)
- GET /datasets - list all datasets

UK dataset: Look for name containing "enhanced_frs"
US dataset: Look for name containing "enhanced_cps"

### Policies (reform specifications)
- POST /policies - create policy reform
- GET /policies - list all policies
- GET /policies/{{id}} - get policy details

## TIPS

1. Always search for parameters FIRST before creating policies
2. Use the exact parameter_id (UUID) from the search results
3. Poll async endpoints until status="completed" (may take 10-60 seconds)
4. For UK, use year=2026; for US, use year=2024
5. The result contains calculated values for all variables (income_tax, net_income, etc.)
6. Economic impact takes longer (30-120 seconds) as it simulates the full population"""


@app.function(image=sandbox_image, secrets=[anthropic_secret], timeout=600)
def stream_policy_analysis(
    question: str, api_base_url: str = "https://v2.api.policyengine.org"
):
    """Stream Claude Code output line by line.

    Uses direct API calls instead of MCP (MCP doesn't work in Modal containers).
    Claude is given a system prompt explaining how to use the PolicyEngine API.
    """
    import subprocess

    system_prompt = _get_api_system_prompt(api_base_url)

    print(f"[MODAL] Starting Claude Code (streaming) for question: {question[:100]}")

    # Use Popen for streaming output - no MCP, use system prompt instead
    # stdin=DEVNULL prevents Claude from waiting for input (critical!)
    process = subprocess.Popen(
        [
            "claude",
            "-p",
            question,
            "--system-prompt",
            system_prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--max-turns",
            "10",
            "--allowedTools",
            "Bash,WebFetch,Read,Write,Edit",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,  # Line buffered
    )

    # Yield each line as it comes
    for line in process.stdout:
        if line.strip():
            print(f"[MODAL] Claude output: {line[:100]}")
            yield line

    process.wait()
    print(f"[MODAL] Claude Code finished with returncode: {process.returncode}")


@app.function(
    image=sandbox_image, secrets=[anthropic_secret, logfire_secret], timeout=600
)
def run_policy_analysis(
    question: str, api_base_url: str = "https://v2.api.policyengine.org"
) -> dict:
    """Run Claude Code to answer a policy question.

    This is the non-streaming version that returns the full result.
    """
    import os
    import subprocess

    import logfire

    # Only configure logfire if token is available
    if os.environ.get("LOGFIRE_TOKEN"):
        logfire.configure(
            service_name="policyengine-agent-sandbox",
            token=os.environ["LOGFIRE_TOKEN"],
        )

    with logfire.span(
        "run_policy_analysis", question=question[:100], api_base_url=api_base_url
    ):
        # MCP config for Claude Code (type: sse for HTTP SSE transport)
        mcp_config = {
            "mcpServers": {
                "policyengine": {"type": "sse", "url": f"{api_base_url}/mcp"}
            }
        }
        mcp_config_json = json.dumps(mcp_config)

        logfire.info(
            "Starting Claude Code",
            question=question[:100],
            mcp_url=f"{api_base_url}/mcp",
        )

        # Run Claude Code with --mcp-config (no --dangerously-skip-permissions as root)
        result = subprocess.run(
            [
                "claude",
                "-p",
                question,
                "--mcp-config",
                mcp_config_json,
                "--max-turns",
                "10",
                "--allowedTools",
                "mcp__policyengine__*,Bash,Read,Grep,Glob,Write,Edit",
            ],
            capture_output=True,
            text=True,
            timeout=540,
        )

        logfire.info(
            "Claude Code finished",
            returncode=result.returncode,
            stdout_len=len(result.stdout),
            stderr_len=len(result.stderr),
        )

        if result.returncode != 0:
            logfire.error("Claude Code failed", stderr=result.stderr[:500])

        return {
            "status": "completed" if result.returncode == 0 else "failed",
            "report": result.stdout,
            "error": result.stderr if result.returncode != 0 else None,
        }


# For local testing
if __name__ == "__main__":
    import sys

    question = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "How much would it cost to set the UK basic rate to 19p?"
    )

    print(f"Question: {question}\n")
    print("=" * 60)

    # Run via Modal
    with modal.enable_local():
        result = run_policy_analysis.local(question)
        print(result["report"])
        if result["error"]:
            print(f"\nError: {result['error']}")
