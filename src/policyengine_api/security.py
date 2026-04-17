"""Security utilities: HMAC-signed identifiers and request verification.

The agent callback endpoints (/agent/log/{call_id}, /agent/complete/{call_id})
must not trust opaque identifiers from the public internet. A caller that
knows or guesses a call_id must not be able to inject logs or mark runs
complete with arbitrary payloads.

To protect those endpoints without introducing a full auth stack we issue
HMAC-signed call IDs. The spawner creates ``raw_id`` and ``tag = HMAC(key,
raw_id)``, bundles them into ``call_id = f"{raw_id}.{tag}"`` and returns the
signed value to the caller. Logging/completion requests echo back the signed
id in the URL; the endpoints verify the tag before trusting the request.

The signing key lives in ``settings.agent_callback_secret``. In dev the
secret defaults to a random per-process value (which invalidates signatures
across restarts); production deploys must supply it via the environment.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid

from fastapi import Header, HTTPException, Path

from policyengine_api.config.settings import settings

# Separator between the random identifier and HMAC tag. Chosen so it never
# appears in the URL-encoded random portion (hex) or the hex-encoded tag.
_SEPARATOR = "."


def _signing_key() -> bytes:
    """Return the HMAC key for agent callbacks.

    Falls back to a process-scoped random value in development so logs/complete
    requests issued by the same process remain valid. This prevents attackers
    from using a leaked dev default, at the cost of losing callbacks across
    restarts. Production must set ``AGENT_CALLBACK_SECRET`` (or the settings
    equivalent) explicitly.
    """
    configured = settings.agent_callback_secret
    if configured:
        return configured.encode("utf-8")
    return _DEV_SECRET


def _compute_tag(raw_id: str) -> str:
    return hmac.new(_signing_key(), raw_id.encode("utf-8"), hashlib.sha256).hexdigest()[
        :32
    ]


def issue_signed_call_id(prefix: str = "fc-") -> str:
    """Generate a signed call id of the form ``{prefix}{random}.{tag}``.

    The random portion is 24 hex characters (96 bits) — enough entropy that
    even without the signature, brute-force lookups are infeasible.
    """
    raw = f"{prefix}{uuid.uuid4().hex[:24]}"
    return f"{raw}{_SEPARATOR}{_compute_tag(raw)}"


def verify_signed_call_id(call_id: str) -> str:
    """Constant-time verify an incoming signed call id.

    Returns the same ``call_id`` on success (so callers can use it as the
    storage key). Raises ``HTTPException(401)`` on mismatch to avoid leaking
    which part was wrong.
    """
    if not isinstance(call_id, str) or _SEPARATOR not in call_id:
        raise HTTPException(status_code=401, detail="Invalid call id signature")

    raw_id, _, tag = call_id.rpartition(_SEPARATOR)
    if not raw_id or not tag:
        raise HTTPException(status_code=401, detail="Invalid call id signature")

    expected = _compute_tag(raw_id)
    if not hmac.compare_digest(expected, tag):
        raise HTTPException(status_code=401, detail="Invalid call id signature")

    return call_id


async def verified_call_id(
    call_id: str = Path(..., description="Signed agent call identifier"),
) -> str:
    """FastAPI dependency that validates a signed call id path parameter."""
    return verify_signed_call_id(call_id)


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """Verify the incoming API key against the configured shared secret.

    Used to gate destructive/privileged endpoints (e.g. ``/analysis/rerun``)
    that are not tied to a signed identifier. The key is read from the
    ``X-API-Key`` header.
    """
    expected = settings.api_key
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="API key is not configured on the server",
        )
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# ---------------------------------------------------------------------------
# Module-scoped dev fallback secret. Computed once so signatures stay stable
# for the lifetime of a single process when no secret is configured.
# ---------------------------------------------------------------------------
_DEV_SECRET = secrets.token_bytes(32)
