# Build docs
FROM oven/bun:1 AS docs-builder
WORKDIR /docs
COPY docs/package.json docs/bun.lock ./
RUN bun install
COPY docs/ ./
RUN bun run build

# Build API
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

# Install bun and Claude Code CLI (symlink bun as node for CLI compatibility)
COPY --from=docs-builder /usr/local/bin/bun /usr/local/bin/bun
RUN ln -s /usr/local/bin/bun /usr/local/bin/node && \
    bun install -g @anthropic-ai/claude-code
ENV PATH="/root/.bun/bin:$PATH"

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY --from=docs-builder /docs/out ./docs/out/

# Install dependencies
RUN uv pip install --system -e .

# Run migrations and start server
CMD uvicorn policyengine_api.main:app --host 0.0.0.0 --port ${API_PORT:-80} --proxy-headers --forwarded-allow-ips='*'
