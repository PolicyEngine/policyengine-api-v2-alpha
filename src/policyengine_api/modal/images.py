"""Modal image definitions with exact version pins.

Country packages use exact pins (==) instead of loose pins (>=).
The version is read from environment variables set during deployment,
ensuring deterministic builds and version coexistence.
"""

import os

import modal

US_VERSION = os.environ.get("POLICYENGINE_US_VERSION", "1.592.4")
UK_VERSION = os.environ.get("POLICYENGINE_UK_VERSION", "2.75.1")

base_image = (
    modal.Image.debian_slim(python_version="3.13")
    .apt_install("libhdf5-dev", "git")
    .pip_install("uv")
    .run_commands(
        "uv pip install --system --upgrade "
        "policyengine>=3.2.0 "
        "sqlmodel>=0.0.22 "
        "psycopg2-binary>=2.9.10 "
        "supabase>=2.10.0 "
        "rich>=13.9.4 "
        "logfire[httpx]>=3.0.0 "
        "pydantic-settings>=2.0.0 "
        "tables>=3.10.0"
    )
    .add_local_python_source("policyengine_api", copy=True)
)


def _import_uk():
    """Import UK model at build time to snapshot in memory."""
    from policyengine.tax_benefit_models.uk import uk_latest  # noqa: F401

    print("UK model loaded and snapshotted")


def _import_us():
    """Import US model at build time to snapshot in memory."""
    from policyengine.tax_benefit_models.us import us_latest  # noqa: F401

    print("US model loaded and snapshotted")


# Exact version pins (critical change from the old >= pins)
uk_image = base_image.run_commands(
    f"uv pip install --system policyengine-uk=={UK_VERSION}"
).run_function(_import_uk)

us_image = base_image.run_commands(
    f"uv pip install --system policyengine-us=={US_VERSION}"
).run_function(_import_us)
