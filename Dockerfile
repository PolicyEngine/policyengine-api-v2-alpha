# Build docs (pin Bun version - 1.3.5 has segfault bugs with Next.js)
FROM oven/bun:1.1.42 AS docs-builder
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

# Copy dependency files first (change rarely)
COPY pyproject.toml uv.lock README.md ./

# Create minimal package stub for editable install
RUN mkdir -p src/policyengine_api && touch src/policyengine_api/__init__.py

# Install dependencies (cached unless pyproject.toml or uv.lock change)
RUN --mount=type=cache,target=/root/.cache/uv uv pip install --system -e .

# Copy actual source code (changes frequently, but deps already cached)
COPY src/ ./src/
COPY --from=docs-builder /docs/out ./docs/out/

# Start server
CMD uvicorn policyengine_api.main:app --host 0.0.0.0 --port ${API_PORT:-80} --proxy-headers --forwarded-allow-ips='*'
