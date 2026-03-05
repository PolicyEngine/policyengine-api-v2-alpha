"""Shared constants for the PolicyEngine API."""

from typing import Literal

# Countries supported by the API
CountryId = Literal["us", "uk"]

# Mapping from country ID to tax-benefit model name in the database
COUNTRY_MODEL_NAMES: dict[str, str] = {
    "uk": "policyengine-uk",
    "us": "policyengine-us",
}
