from contextlib import asynccontextmanager

import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from rich.console import Console

from policyengine_api.api import api_router
from policyengine_api.config.settings import settings
from policyengine_api.services.database import init_db

console = Console()

# Configure Logfire (only if token is set)
if settings.logfire_token:
    logfire.configure(
        service_name="policyengine-api",
        token=settings.logfire_token,
        environment=settings.logfire_environment,
        console=False,
    )
    logfire.instrument_httpx()


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
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instrument FastAPI with Logfire
logfire.instrument_fastapi(app)

app.include_router(api_router)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
