from __future__ import annotations

import functools
from typing import Any


class BundleMetadataUnavailable(RuntimeError):
    """Raised when the installed policyengine package cannot expose a bundle."""


@functools.lru_cache(maxsize=1)
def current_bundle_metadata(*, strict: bool = False) -> dict[str, Any]:
    """Return bundle metadata from the installed policyengine package."""

    try:
        import policyengine.bundle as pe_bundle
    except Exception as exc:  # pragma: no cover - import failure shape is env-specific
        if strict:
            raise BundleMetadataUnavailable(
                "Installed policyengine package does not expose bundle metadata."
            ) from exc
        return {
            "available": False,
            "error": "Installed policyengine package does not expose bundle metadata.",
        }

    try:
        if strict:
            pe_bundle.require_bundle(strict=True)
        manifest = pe_bundle.get_bundle_manifest()
    except Exception as exc:
        if strict:
            raise
        return {
            "available": False,
            "error": str(exc),
        }

    return {
        "available": True,
        "policyengine_version": manifest["policyengine"]["version"],
        "bundle_version": manifest["bundle_version"],
        "bundle_digest": manifest.get("bundle_digest"),
        "profiles": {
            profile_name: {
                "packages": profile.get("packages", []),
                "countries": profile.get("countries", []),
                "install_targets": profile.get("install_targets", {}),
            }
            for profile_name, profile in manifest.get("profiles", {}).items()
        },
        "packages": manifest.get("packages", {}),
        "validation_report": manifest.get("validation_report"),
    }


def reset_bundle_metadata_cache() -> None:
    current_bundle_metadata.cache_clear()
