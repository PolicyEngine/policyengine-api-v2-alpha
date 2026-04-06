"""Shared constants for the PolicyEngine API."""

from typing import Literal

# Countries supported by the API
CountryId = Literal["us", "uk"]

# Expected model name prefix — all model names follow "policyengine-{country_id}"
MODEL_NAME_PREFIX = "policyengine-"

# Mapping from country ID to tax-benefit model name in the database
COUNTRY_MODEL_NAMES: dict[str, str] = {
    "uk": "policyengine-uk",
    "us": "policyengine-us",
}

# Reverse mapping: model name → country ID
MODEL_NAME_TO_COUNTRY: dict[str, str] = {v: k for k, v in COUNTRY_MODEL_NAMES.items()}


def country_id_from_model_name(model_name: str) -> str:
    """Extract country ID from a model name.

    Model names follow the convention "policyengine-{country_id}"
    (e.g., "policyengine-us", "policyengine-uk", "policyengine-ca").

    This is forward-compatible with new countries — it strips the
    known prefix rather than checking against a hardcoded list.

    Raises:
        ValueError: If the model name doesn't start with the expected prefix.
    """
    if not model_name.startswith(MODEL_NAME_PREFIX):
        raise ValueError(
            f"Model name '{model_name}' does not start with "
            f"expected prefix '{MODEL_NAME_PREFIX}'"
        )
    return model_name[len(MODEL_NAME_PREFIX):]
