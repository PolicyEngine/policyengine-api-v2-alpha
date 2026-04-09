"""
Update Modal version registries after deployment.

Each deployment creates a versioned app (e.g., policyengine-v2-us1-592-4-uk2-75-1).
This script updates the v2-specific version dicts to map package versions to
app names.

The dicts allow Cloud Run to route requests for specific versions to the
correct versioned Modal app. Multiple versions coexist — old deployments
remain accessible via their version numbers.

Usage:
    uv run python scripts/update_version_registry.py \
        --app-name policyengine-v2-us1-592-4-uk2-75-1 \
        --us-version 1.592.4 \
        --uk-version 2.75.1 \
        --environment staging
"""

import argparse

import modal


def _upsert_entry(
    version_dict: modal.Dict,
    dict_name: str,
    key: str,
    value: str,
) -> None:
    """Insert or update a single Dict entry, logging the change."""
    try:
        previous = version_dict[key]
        if previous != value:
            print(f"  {dict_name}[{key}]: {previous} -> {value}")
        else:
            print(f"  {dict_name}[{key}]: {value} (unchanged)")
    except KeyError:
        print(f"  {dict_name}[{key}]: (new) -> {value}")

    version_dict[key] = value


def _update_latest(
    version_dict: modal.Dict,
    dict_name: str,
    version: str,
) -> None:
    """Update the 'latest' pointer, logging the change."""
    _upsert_entry(version_dict, dict_name, "latest", version)


def update_version_dict(
    dict_name: str,
    environment: str,
    version: str,
    app_name: str,
) -> None:
    """Update a version dict: set version → app_name and latest → version.

    Args:
        dict_name: Name of the Modal Dict (e.g., "api-v2-us-versions")
        environment: Modal environment (staging or main)
        version: Package version (e.g., "1.592.4")
        app_name: App name to map this version to
    """
    version_dict = modal.Dict.from_name(
        dict_name,
        environment_name=environment,
        create_if_missing=True,
    )

    _upsert_entry(version_dict, dict_name, version, app_name)
    _update_latest(version_dict, dict_name, version)


def main():
    parser = argparse.ArgumentParser(
        description="Update version registries after Modal deployment"
    )
    parser.add_argument(
        "--app-name",
        required=True,
        help="Versioned app name (e.g., policyengine-v2-us1-592-4-uk2-75-1)",
    )
    parser.add_argument(
        "--us-version",
        required=True,
        help="US package version (e.g., 1.592.4)",
    )
    parser.add_argument(
        "--uk-version",
        required=True,
        help="UK package version (e.g., 2.75.1)",
    )
    parser.add_argument(
        "--environment",
        required=True,
        help="Modal environment (staging or main)",
    )
    args = parser.parse_args()

    print(f"Updating version registries in Modal environment: {args.environment}")
    print(f"  App name: {args.app_name}")
    print(f"  US version: {args.us_version}")
    print(f"  UK version: {args.uk_version}")
    print()

    print("US version registry:")
    update_version_dict(
        "api-v2-us-versions",
        args.environment,
        args.us_version,
        args.app_name,
    )
    print()

    print("UK version registry:")
    update_version_dict(
        "api-v2-uk-versions",
        args.environment,
        args.uk_version,
        args.app_name,
    )
    print()

    print("Version registries updated successfully.")


if __name__ == "__main__":
    main()
