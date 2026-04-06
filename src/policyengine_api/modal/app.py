"""Versioned Modal app definition.

The app name is dynamically generated from country package versions,
allowing multiple versions to coexist as separate Modal apps.

Environment variables:
  MODAL_APP_NAME: Override the generated app name (optional)
  POLICYENGINE_US_VERSION: US package version (e.g., "1.592.4")
  POLICYENGINE_UK_VERSION: UK package version (e.g., "2.75.1")
"""

import os

import modal

US_VERSION = os.environ.get("POLICYENGINE_US_VERSION", "1.592.4")
UK_VERSION = os.environ.get("POLICYENGINE_UK_VERSION", "2.75.1")


def get_app_name(us_version: str, uk_version: str) -> str:
    """Generate a versioned app name from country package versions.

    Dots in version strings are replaced with dashes for Modal
    compatibility.

    Example: get_app_name("1.592.4", "2.75.1")
             -> "policyengine-v2-us1-592-4-uk2-75-1"
    """
    us_safe = us_version.replace(".", "-")
    uk_safe = uk_version.replace(".", "-")
    return f"policyengine-v2-us{us_safe}-uk{uk_safe}"


APP_NAME = os.environ.get(
    "MODAL_APP_NAME", get_app_name(US_VERSION, UK_VERSION)
)

app = modal.App(APP_NAME)

# Secrets for database and observability
db_secrets = modal.Secret.from_name("policyengine-db")
logfire_secrets = modal.Secret.from_name("policyengine-logfire")
