"""Modal Sandbox for running Claude Code with PolicyEngine MCP server.

This runs the actual Claude Code CLI in an isolated sandbox, connected
to the PolicyEngine API via MCP. Outputs are streamed back in real-time.
"""

import modal

# Sandbox image with Bun and Claude Code CLI (v2 - with ToS pre-accept)
sandbox_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("curl", "git", "unzip")
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


def run_claude_code_in_sandbox(
    question: str,
    api_base_url: str = "https://v2.api.policyengine.org",
) -> tuple[modal.Sandbox, any]:
    """Create a sandbox running Claude Code with MCP server configured.

    Returns the sandbox and process handle for streaming output.
    """
    import logfire

    print("[SANDBOX] run_claude_code_in_sandbox starting", flush=True)
    logfire.info(
        "run_claude_code_in_sandbox: starting",
        question=question[:100],
        api_base_url=api_base_url,
    )

    # MCP config for Claude Code (type: sse for HTTP SSE transport)
    mcp_config = f"""{{
  "mcpServers": {{
    "policyengine": {{
      "type": "sse",
      "url": "{api_base_url}/mcp"
    }}
  }}
}}"""

    # Get reference to deployed app (required when calling from outside Modal)
    print("[SANDBOX] looking up Modal app", flush=True)
    logfire.info("run_claude_code_in_sandbox: looking up Modal app")
    sandbox_app = modal.App.lookup("policyengine-sandbox", create_if_missing=True)
    print("[SANDBOX] Modal app found", flush=True)
    logfire.info("run_claude_code_in_sandbox: Modal app found")

    print("[SANDBOX] creating sandbox", flush=True)
    logfire.info("run_claude_code_in_sandbox: creating sandbox")
    sb = modal.Sandbox.create(
        app=sandbox_app,
        image=sandbox_image,
        secrets=[anthropic_secret, logfire_secret],
        timeout=600,
        workdir="/tmp",
    )
    print("[SANDBOX] sandbox created", flush=True)
    logfire.info("run_claude_code_in_sandbox: sandbox created")

    # Write MCP config
    logfire.info("run_claude_code_in_sandbox: writing MCP config")
    sb.exec("mkdir", "-p", "/root/.claude")
    config_process = sb.exec(
        "sh", "-c", f"cat > /root/.claude/mcp_servers.json << 'EOF'\n{mcp_config}\nEOF"
    )
    config_process.wait()
    logfire.info(
        "run_claude_code_in_sandbox: MCP config written",
        returncode=config_process.returncode,
    )

    # Run Claude Code with the question
    # Note: Can't use --dangerously-skip-permissions as root (Modal runs as root)
    # --max-turns: limit execution to prevent runaway
    print("[SANDBOX] Starting claude CLI with question", flush=True)
    logfire.info("run_claude_code_in_sandbox: starting claude CLI")
    process = sb.exec(
        "claude",
        "-p",
        question,
        "--output-format",
        "stream-json",
        "--verbose",
        "--max-turns",
        "10",
        "--allowedTools",
        "mcp__policyengine__*,Bash,Read,Grep,Glob,Write,Edit",
    )
    print("[SANDBOX] claude CLI process started", flush=True)
    logfire.info("run_claude_code_in_sandbox: claude CLI process started, returning")

    return sb, process


@app.function(
    image=sandbox_image, secrets=[anthropic_secret, logfire_secret], timeout=600
)
def run_policy_analysis(
    question: str, api_base_url: str = "https://v2.api.policyengine.org"
) -> dict:
    """Run Claude Code to answer a policy question.

    This is the non-streaming version that returns the full result.
    """
    import json
    import os
    import subprocess

    import logfire

    logfire.configure(service_name="policyengine-agent-sandbox")

    with logfire.span(
        "run_policy_analysis", question=question[:100], api_base_url=api_base_url
    ):
        # Write MCP config
        os.makedirs("/root/.claude", exist_ok=True)
        mcp_config = {
            "mcpServers": {
                "policyengine": {"type": "sse", "url": f"{api_base_url}/mcp"}
            }
        }
        with open("/root/.claude/mcp_servers.json", "w") as f:
            json.dump(mcp_config, f)

        logfire.info("Starting Claude Code", question=question[:100])

        # Run Claude Code (no --dangerously-skip-permissions since we run as root)
        result = subprocess.run(
            [
                "claude",
                "-p",
                question,
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
