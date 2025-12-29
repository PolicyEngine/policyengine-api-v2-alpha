"""Modal Sandbox for running Claude Code with PolicyEngine MCP server.

This runs the Claude Code CLI connected to the PolicyEngine API via MCP.
Logs are POSTed back to the API for real-time streaming to the UI.
"""

import json
import subprocess

import modal
import requests

# Sandbox image with Bun and Claude Code CLI
sandbox_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("curl", "git", "unzip")
    .pip_install("requests")
    .run_commands(
        # Install Bun
        "curl -fsSL https://bun.sh/install | bash",
        # Add bun to PATH, create node symlink (Claude CLI needs it), install Claude Code
        "export BUN_INSTALL=/root/.bun && export PATH=$BUN_INSTALL/bin:$PATH && "
        "ln -s $BUN_INSTALL/bin/bun /usr/local/bin/node && "
        "bun install -g @anthropic-ai/claude-code",
        # Pre-accept ToS and configure for non-interactive use
        "mkdir -p /root/.claude && "
        'echo \'{"hasCompletedOnboarding": true, "hasAcknowledgedCostThreshold": true}\' '
        "> /root/.claude/settings.json",
    )
    .env(
        {
            "BUN_INSTALL": "/root/.bun",
            "PATH": "/root/.bun/bin:/usr/local/bin:/usr/bin:/bin",
            "CLAUDE_CODE_SKIP_ONBOARDING": "1",
        }
    )
)

app = modal.App("policyengine-sandbox")

# Secrets
anthropic_secret = modal.Secret.from_name("anthropic-api-key")


def post_log(api_base_url: str, call_id: str, message: str) -> None:
    """POST a log entry to the API."""
    try:
        requests.post(
            f"{api_base_url}/agent/log/{call_id}",
            json={"message": message},
            timeout=5,
        )
    except Exception:
        pass  # Don't fail on log errors


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


@app.function(image=sandbox_image, secrets=[anthropic_secret], timeout=600)
def run_agent(
    question: str,
    api_base_url: str = "https://v2.api.policyengine.org",
    call_id: str = "",
) -> dict:
    """Run Claude Code with MCP server to answer a policy question.

    Logs are POSTed back to the API for real-time streaming.
    """

    def log(msg: str) -> None:
        print(msg)  # Also print for debugging
        if call_id:
            post_log(api_base_url, call_id, msg)

    log(f"[AGENT] Starting analysis for: {question[:200]}")
    log(f"[AGENT] API URL: {api_base_url}")
    log(f"[AGENT] MCP endpoint: {api_base_url}/mcp")

    # MCP config for Claude Code - connects to PolicyEngine API's MCP server
    mcp_config = {
        "mcpServers": {"policyengine": {"type": "sse", "url": f"{api_base_url}/mcp"}}
    }
    mcp_config_json = json.dumps(mcp_config)

    log(f"[AGENT] MCP config: {mcp_config_json}")

    # Build command
    cmd = [
        "claude",
        "-p",
        question,
        "--mcp-config",
        mcp_config_json,
        "--output-format",
        "stream-json",
        "--verbose",
        "--max-turns",
        "15",
        "--allowedTools",
        "mcp__policyengine__*,Bash,WebFetch,Read,Write,Edit",
    ]

    log(f"[AGENT] Running: {' '.join(cmd[:5])}...")

    # Run Claude Code - stdin=DEVNULL prevents hanging
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,  # Line buffered
    )

    # Stream output
    full_output = []
    final_result = None

    for line in process.stdout:
        line = line.rstrip()
        if line:
            log(f"[CLAUDE] {line}")
            full_output.append(line)

            # Try to parse stream-json events
            try:
                event = json.loads(line)
                # Capture the final result
                if event.get("type") == "result":
                    final_result = event.get("result", "")
            except json.JSONDecodeError:
                pass

    process.wait()
    log(f"[AGENT] Claude exited with code: {process.returncode}")

    result = {
        "status": "completed" if process.returncode == 0 else "failed",
        "result": final_result,
        "returncode": process.returncode,
        "output_lines": len(full_output),
    }

    # Notify API of completion
    if call_id:
        post_complete(api_base_url, call_id, result)

    return result


# For local testing
if __name__ == "__main__":
    import sys

    question = (
        sys.argv[1] if len(sys.argv) > 1 else "What is the UK basic rate of income tax?"
    )

    print(f"Question: {question}\n")
    print("=" * 60)

    # Run via Modal
    with modal.enable_local():
        result = run_agent.local(question)
        print("\n" + "=" * 60)
        print(f"Result: {result}")
