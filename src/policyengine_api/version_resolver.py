"""
Resolve policyengine package versions to versioned Modal app names.

Uses Modal Dicts as a version registry:
  - simulation-api-us-versions: maps US version strings -> app names
  - simulation-api-uk-versions: maps UK version strings -> app names

Each dict also has a "latest" key pointing to the current default version.

Cloud Run reads these dicts to determine which versioned Modal app to
spawn simulation functions on. This replaces the hardcoded
"policyengine" app name with dynamic, version-aware routing.

Temporary infrastructure — deleted in Phase 5 cleanup when v1 is removed.
"""

import functools
import logging

import modal

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=32)
def _resolve_app_name(
    country: str, version: str | None, environment: str
) -> str:
    """Look up the Modal app name for a given country+version from Modal Dicts.

    Args:
        country: "us" or "uk"
        version: Specific version string (e.g. "1.592.4"), or None for latest
        environment: Modal environment name ("staging" or "main")

    Returns:
        The versioned Modal app name (e.g. "policyengine-us1-592-4-uk2-75-1")

    Raises:
        KeyError: If version not found in registry
    """
    dict_name = f"simulation-api-{country.lower()}-versions"
    version_dict = modal.Dict.from_name(
        dict_name, environment_name=environment
    )

    if version is None:
        resolved_version = version_dict["latest"]
    else:
        resolved_version = version

    return version_dict[resolved_version]


def resolve_modal_function(
    function_name: str,
    country: str,
    version: str | None = None,
) -> modal.Function:
    """Resolve a Modal function reference for the given country and version.

    Args:
        function_name: Name of the Modal function
            (e.g. "simulate_household_uk")
        country: "us" or "uk"
        version: Specific version string, or None for latest

    Returns:
        modal.Function reference ready to .spawn() or .remote()
    """
    from policyengine_api.config import settings

    try:
        app_name = _resolve_app_name(
            country, version, settings.modal_environment
        )
        return modal.Function.from_name(
            app_name,
            function_name,
            environment_name=settings.modal_environment,
        )
    except (KeyError, modal.exception.NotFoundError):
        logger.warning(
            "Version registry lookup failed for %s/%s, "
            "falling back to legacy app 'policyengine'",
            country,
            version,
        )
        return modal.Function.from_name(
            "policyengine",
            function_name,
            environment_name=settings.modal_environment,
        )
