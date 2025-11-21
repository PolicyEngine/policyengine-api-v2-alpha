from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from redis import asyncio as aioredis
from rich.console import Console
import logfire

from policyengine_api.api import api_router
from policyengine_api.config.settings import settings
from policyengine_api.services.database import init_db

console = Console()

# Configure Logfire
logfire.configure(service_name="policyengine-api")
logfire.instrument_httpx()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and cache on startup."""
    console.print("[bold green]Initializing database...[/bold green]")
    init_db()
    console.print("[bold green]Database initialized[/bold green]")

    console.print("[bold green]Initializing cache...[/bold green]")
    redis = aioredis.from_url(settings.redis_url, encoding="utf8", decode_responses=True)
    FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")
    console.print("[bold green]Cache initialized[/bold green]")

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
