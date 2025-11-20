FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install dependencies
RUN uv pip install --system -e .

# Run migrations and start server
CMD ["uvicorn", "policyengine_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
