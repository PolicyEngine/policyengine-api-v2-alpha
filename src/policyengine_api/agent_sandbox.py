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
    return f"""You are a PolicyEngine policy analyst. Answer questions about tax and benefit policy using the PolicyEngine API.

## PolicyEngine API ({api_base_url})

Use curl or WebFetch to call these endpoints. All responses are JSON.

### Key endpoints:

**Variables** (tax/benefit concepts):
- GET /variables - list all variables
- GET /variables/{{variable_id}} - get variable details (e.g. income_tax, universal_credit)

**Parameters** (policy levers):
- GET /parameters - list all parameters
- GET /parameters/{{parameter_id}} - get parameter details (e.g. gov.hmrc.income_tax.rates.uk)

**Household calculations**:
- POST /household/calculate - calculate a household's taxes/benefits
  Body: {{"country": "uk"|"us", "household": {{...}}, "policy": {{...}}}}
  Returns: job_id to poll
- GET /household/calculate/{{job_id}} - poll for results

**Economic impact** (macro analysis):
- POST /economic-impact - run economy-wide simulation
  Body: {{"country": "uk"|"us", "policy": {{...}}, "dataset": "enhanced_cps"|"enhanced_frs"}}
  Returns: report_id to poll
- GET /analysis/economic-impact/{{report_id}} - poll for results

### Example workflow:

1. Find relevant parameter: curl {api_base_url}/parameters?search=basic_rate
2. Create reform policy with new value
3. Submit calculation: curl -X POST {api_base_url}/household/calculate -d '{{...}}'
4. Poll for results: curl {api_base_url}/household/calculate/{{job_id}}

### Tips:
- UK uses "enhanced_frs" dataset, US uses "enhanced_cps"
- Poll endpoints until status="completed"
- Household structure uses person/household/family entities
- Policy reforms specify parameter paths and new values by date"""


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
