from contextlib import asynccontextmanager
from pathlib import Path

import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_mcp import FastApiMCP
from rich.console import Console

from policyengine_api.api import api_router
from policyengine_api.config.settings import settings
from policyengine_api.services.database import init_db

console = Console()

# Configure Logfire (only if token is set)
_logfire_enabled = bool(settings.logfire_token)
if _logfire_enabled:

    def _scrubbing_callback(m: logfire.ScrubMatch):
        """Allow 'session' through for Claude stream debugging."""
        if m.path in (("attributes", "line"), ("attributes", "line_preview")):
            if m.pattern_match.group(0) == "session":
                return m.value

    logfire.configure(
        service_name="policyengine-api",
        token=settings.logfire_token,
        environment=settings.logfire_environment,
        console=False,
        scrubbing=logfire.ScrubbingOptions(callback=_scrubbing_callback),
    )
    logfire.instrument_httpx()

    # Disable noisy SQLAlchemy auto-instrumentation
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().uninstrument()
    except ImportError:
        pass  # Not installed


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and cache on startup."""
    console.print("[bold green]Initializing database...[/bold green]")
    init_db()
    console.print("[bold green]Database initialized[/bold green]")

    console.print("[bold green]Initializing cache...[/bold green]")
    FastAPICache.init(InMemoryBackend(), prefix="fastapi-cache")
    console.print("[bold green]Cache initialized[/bold green]")

    yield


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    debug=settings.debug,
    lifespan=lifespan,
    redirect_slashes=True,
    docs_url=None,  # Disable default Swagger UI - we serve custom docs
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instrument FastAPI with Logfire (only if configured)
if _logfire_enabled:
    logfire.instrument_fastapi(app, excluded_urls=["/health"])

app.include_router(api_router)

# Mount MCP server - exposes all API endpoints as MCP tools at /mcp
# Using mount_sse() for Server-Sent Events transport (required by Claude Code)
mcp = FastApiMCP(app)
mcp.mount_sse(mount_path="/mcp")

# Mount static docs site at /docs (built from Next.js in docs/out)
docs_path = Path(__file__).parent.parent.parent / "docs" / "out"
if docs_path.exists():
    app.mount("/docs", StaticFiles(directory=docs_path, html=True), name="docs")


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
