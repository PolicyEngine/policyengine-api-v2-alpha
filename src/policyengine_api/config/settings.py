from importlib.metadata import version

from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_version() -> str:
    try:
        return version("policyengine-api-v2")
    except Exception:
        return "0.0.0-dev"


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # Supabase
    supabase_url: str = "http://localhost:54321"
    supabase_key: str = ""
    supabase_secret_key: str = ""
    supabase_db_url: str = ""

    # Worker
    worker_poll_interval: int = 60  # seconds
    worker_port: int = 8080

    # Storage
    storage_bucket: str = "datasets"

    # Logfire
    logfire_token: str = ""
    logfire_environment: str = "local"

    # API
    api_title: str = "PolicyEngine API v2"
    api_version: str = _get_version()
    api_port: int = 8000
    debug: bool = False

    # Seeding
    limit_seed_parameters: bool = False
    hugging_face_token: str = ""

    # Agent
    anthropic_api_key: str = ""
    agent_use_modal: bool = False
    policyengine_api_url: str = "https://v2.api.policyengine.org"
    # HMAC secret used to sign agent callback identifiers. If unset the
    # security module falls back to a per-process random value.
    agent_callback_secret: str = ""

    # Shared API key used to gate destructive/privileged endpoints.
    api_key: str = ""

    # Modal
    modal_environment: str = "main"

    @property
    def database_url(self) -> str:
        """Get database URL from Supabase.

        For local development, the database runs on port 54322 (not 54321
        which is the API). Use ``supabase_db_url`` to override, or rely on
        the default local URL.

        We deliberately do not synthesise a ``postgres:postgres@...`` URL for
        remote Supabase deployments — the fallback would leak credentials
        into whatever Supabase hostname the caller pointed at, and any
        production deployment that arrived at that branch has misconfigured
        ``supabase_db_url`` and should fail loudly.
        """
        if self.supabase_db_url:
            return self.supabase_db_url

        # For local development, default to the standard Supabase local DB port
        if "localhost" in self.supabase_url or "127.0.0.1" in self.supabase_url:
            return "postgresql://postgres:postgres@127.0.0.1:54322/postgres"

        raise ValueError(
            "supabase_db_url must be configured for non-local Supabase. "
            "Set SUPABASE_DB_URL (e.g. "
            "postgresql://user:pass@db.project.supabase.co:5432/postgres)."
        )


settings = Settings()
