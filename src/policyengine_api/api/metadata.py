from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from policyengine_api.services.bundle_metadata import current_bundle_metadata

router = APIRouter(prefix="/metadata", tags=["metadata"])


@router.get("/bundle")
def get_bundle_metadata() -> dict[str, Any]:
    """Return the policyengine bundle metadata used by this API process."""

    return current_bundle_metadata()
