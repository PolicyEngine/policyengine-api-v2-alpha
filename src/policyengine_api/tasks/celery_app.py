from celery import Celery
import logfire

from policyengine_api.config.settings import settings

# Configure Logfire for worker
logfire.configure(
    service_name="policyengine-worker",
    token=settings.logfire_token if settings.logfire_token else None,
)
logfire.instrument_httpx()

celery_app = Celery(
    "policyengine",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
