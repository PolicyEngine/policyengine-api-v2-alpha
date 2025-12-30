from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # Supabase
    supabase_url: str = "http://localhost:54321"
    supabase_key: str = ""
    supabase_service_key: str = ""
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
    api_version: str = "0.1.0"
    api_port: int = 8000
    debug: bool = False

    # Seeding
    limit_seed_parameters: bool = False
    hugging_face_token: str = ""

    # Agent
    anthropic_api_key: str = ""
    agent_use_modal: bool = False
    policyengine_api_url: str = "https://v2.api.policyengine.org"

    @property
    def database_url(self) -> str:
        """Get database URL from Supabase."""
        return (
            self.supabase_db_url
            or self.supabase_url.replace(
                "http://", "postgresql://postgres:postgres@"
            ).replace("https://", "postgresql://postgres:postgres@")
            + "/postgres"
        )


settings = Settings()
