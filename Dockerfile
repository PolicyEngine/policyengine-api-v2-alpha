# Build docs
FROM node:22-slim AS docs-builder
WORKDIR /docs
COPY docs/package.json docs/bun.lock ./
RUN npm install
COPY docs/ ./
RUN npm run build

# Build API
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY --from=docs-builder /docs/out ./docs/out/

# Install dependencies
RUN uv pip install --system -e .

# Run migrations and start server
CMD uvicorn policyengine_api.main:app --host 0.0.0.0 --port ${API_PORT:-80} --proxy-headers --forwarded-allow-ips='*'
