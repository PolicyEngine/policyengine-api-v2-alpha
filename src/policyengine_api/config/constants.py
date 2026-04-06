"""Shared constants for the PolicyEngine API."""

from typing import Literal

# Countries supported by the API
CountryId = Literal["us", "uk"]

# Mapping from country ID to tax-benefit model name in the database
COUNTRY_MODEL_NAMES: dict[str, str] = {
    "uk": "policyengine-uk",
    "us": "policyengine-us",
}

# Reverse mapping: model name → country ID
MODEL_NAME_TO_COUNTRY: dict[str, str] = {v: k for k, v in COUNTRY_MODEL_NAMES.items()}


def country_id_from_model_name(model_name: str) -> str:
    """Look up country ID from a model name.

    Uses MODEL_NAME_TO_COUNTRY for known models. Raises if the model
    name is not recognized.

    Raises:
        ValueError: If the model name is not in MODEL_NAME_TO_COUNTRY.
    """
    country_id = MODEL_NAME_TO_COUNTRY.get(model_name)
    if country_id is None:
        raise ValueError(
            f"Unknown model name '{model_name}'. "
            f"Known models: {list(MODEL_NAME_TO_COUNTRY.keys())}"
        )
    return country_id
