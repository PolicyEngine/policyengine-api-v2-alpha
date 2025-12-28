"""Modal Sandbox for running Claude Code with PolicyEngine MCP server.

This runs the actual Claude Code CLI in an isolated sandbox, connected
to the PolicyEngine API via MCP. Outputs are streamed back in real-time.
"""

import modal

# Sandbox image with Bun and Claude Code CLI
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
    )
    .env(
        {
            "BUN_INSTALL": "/root/.bun",
            "PATH": "/root/.bun/bin:/usr/local/bin:/usr/bin:/bin",
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

    from policyengine_api.config import settings

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

    # Log from inside the sandbox via Python
    logfire.info("run_claude_code_in_sandbox: logging from inside sandbox")
    escaped_question = question[:50].replace("'", "\\'").replace('"', '\\"')
    sandbox_log = sb.exec(
        "python",
        "-c",
        f"""
import logfire
logfire.configure(token='{settings.logfire_token}', service_name='modal-sandbox-inner')
logfire.info('Inside Modal sandbox', question='{escaped_question}')
print('Logfire configured inside sandbox')
""",
    )
    sandbox_log.wait()
    logfire.info(
        "run_claude_code_in_sandbox: sandbox inner log result",
        stdout=sandbox_log.stdout.read()[:200],
        stderr=sandbox_log.stderr.read()[:200],
        returncode=sandbox_log.returncode,
    )

    # Check environment inside sandbox
    logfire.info("run_claude_code_in_sandbox: checking sandbox environment")
    env_check = sb.exec(
        "sh",
        "-c",
        "which claude && echo PATH=$PATH && echo ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:0:10}...",
    )
    env_check.wait()
    env_stdout = env_check.stdout.read()
    env_stderr = env_check.stderr.read()
    logfire.info(
        "run_claude_code_in_sandbox: env check",
        stdout=env_stdout[:500] if env_stdout else None,
        stderr=env_stderr[:500] if env_stderr else None,
        returncode=env_check.returncode,
    )

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

    # Verify config was written
    verify_process = sb.exec("cat", "/root/.claude/mcp_servers.json")
    verify_process.wait()
    logfire.info(
        "run_claude_code_in_sandbox: MCP config contents",
        config=verify_process.stdout.read()[:500],
    )

    # Test Claude CLI works at all
    print("[SANDBOX] Testing claude --version", flush=True)
    logfire.info("run_claude_code_in_sandbox: testing claude --version")
    version_check = sb.exec("claude", "--version")
    version_check.wait()
    version_stdout = version_check.stdout.read()
    version_stderr = version_check.stderr.read()
    print(f"[SANDBOX] claude --version: stdout={version_stdout}, stderr={version_stderr}, rc={version_check.returncode}", flush=True)
    logfire.info(
        "run_claude_code_in_sandbox: claude --version result",
        stdout=version_stdout[:200] if version_stdout else None,
        stderr=version_stderr[:500] if version_stderr else None,
        returncode=version_check.returncode,
    )

    # Quick test: run Claude with a simple query WITHOUT MCP to verify it works
    print("[SANDBOX] Testing simple claude query (no MCP)", flush=True)
    logfire.info("run_claude_code_in_sandbox: testing simple query without MCP")
    simple_test = sb.exec(
        "claude",
        "-p",
        "Say hello in one word",
        "--output-format",
        "text",
        "--dangerously-skip-permissions",
        "--max-turns",
        "1",
    )
    simple_test.wait()
    simple_stdout = simple_test.stdout.read()
    simple_stderr = simple_test.stderr.read()
    print(f"[SANDBOX] Simple test result: stdout={simple_stdout[:200] if simple_stdout else 'empty'}, stderr={simple_stderr[:200] if simple_stderr else 'empty'}, rc={simple_test.returncode}", flush=True)
    logfire.info(
        "run_claude_code_in_sandbox: simple test result",
        stdout=simple_stdout[:500] if simple_stdout else None,
        stderr=simple_stderr[:500] if simple_stderr else None,
        returncode=simple_test.returncode,
    )

    # Run Claude Code with the question
    # --dangerously-skip-permissions: auto-accept permission prompts (required for non-interactive)
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
        "--dangerously-skip-permissions",
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

        # Run Claude Code
        result = subprocess.run(
            [
                "claude",
                "-p",
                question,
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
