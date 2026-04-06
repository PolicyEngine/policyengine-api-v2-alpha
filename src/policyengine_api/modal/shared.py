"""Shared utilities for Modal functions.

These are plain helper functions (not Modal-decorated) used by all
simulation and comparison functions.
"""


def configure_logfire(service_name: str, traceparent: str | None = None):
    """Configure logfire with optional trace context propagation."""
    import os

    import logfire

    token = os.environ.get("LOGFIRE_TOKEN", "")
    if not token:
        return

    logfire.configure(
        service_name=service_name,
        token=token,
        environment=os.environ.get("LOGFIRE_ENVIRONMENT", "production"),
        console=False,
    )

    if traceparent:
        from opentelemetry import context
        from opentelemetry.trace.propagation.tracecontext import (
            TraceContextTextMapPropagator,
        )

        propagator = TraceContextTextMapPropagator()
        ctx = propagator.extract(carrier={"traceparent": traceparent})
        context.attach(ctx)


def get_database_url() -> str:
    """Get and validate database URL from environment."""
    import os

    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise ValueError(
            "DATABASE_URL environment variable is not set. "
            "The Modal secret 'policyengine-db' must include "
            "DATABASE_URL=postgresql://... "
            "Run: modal run policyengine::validate_secrets to debug."
        )
    if not url.startswith(("postgresql://", "postgres://")):
        raise ValueError(
            f"DATABASE_URL must start with postgresql:// or "
            f"postgres://, got: {url[:50]}..."
        )
    return url


def get_db_session(database_url: str):
    """Create database session."""
    from sqlmodel import Session, create_engine

    engine = create_engine(database_url)
    return Session(engine)


def download_dataset(
    filepath: str,
    supabase_url: str,
    supabase_key: str,
    storage_bucket: str,
) -> str:
    """Download dataset from Supabase storage with local caching."""
    from pathlib import Path

    from supabase import create_client

    cache_dir = Path("/tmp/policyengine_dataset_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / filepath

    if cache_path.exists():
        return str(cache_path)

    client = create_client(supabase_url, supabase_key)
    data = client.storage.from_(storage_bucket).download(filepath)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "wb") as f:
        f.write(data)

    return str(cache_path)
