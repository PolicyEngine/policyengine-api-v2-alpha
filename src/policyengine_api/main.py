from contextlib import asynccontextmanager

from fastapi import FastAPI
from rich.console import Console
import logfire

from policyengine_api.api import api_router
from policyengine_api.config.settings import settings
from policyengine_api.services.database import init_db

console = Console()

# Configure Logfire
logfire.configure()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    console.print("[bold green]Initializing database...[/bold green]")
    init_db()
    console.print("[bold green]Database initialized[/bold green]")
    yield


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    debug=settings.debug,
    lifespan=lifespan,
)

# Instrument FastAPI with Logfire
logfire.instrument_fastapi(app)

app.include_router(api_router)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
