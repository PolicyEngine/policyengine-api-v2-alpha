"""Security helpers for public API guardrails."""

from typing import Annotated

from fastapi import Header, HTTPException, Request, status

from policyengine_api.config.settings import settings


def require_expensive_endpoint_access(
    request: Request,
    x_policyengine_api_key: Annotated[
        str | None, Header(alias="X-PolicyEngine-Api-Key")
    ] = None,
) -> None:
    """Require a shared key for callers of expensive endpoints."""

    expected_key = settings.expensive_endpoint_api_key.strip()
    if expected_key and x_policyengine_api_key == expected_key:
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="X-PolicyEngine-Api-Key header required",
    )
