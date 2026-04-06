"""
Update Modal version registries after deployment.

Each deployment creates a versioned app (e.g., policyengine-us1-592-4-uk2-75-1).
This script updates the version dicts to map package versions to app names.

The dicts allow Cloud Run to route requests for specific versions to the
correct versioned Modal app. Multiple versions coexist — old deployments
remain accessible via their version numbers.

Usage:
    uv run python scripts/update_version_registry.py \
        --app-name policyengine-us1-592-4-uk2-75-1 \
        --us-version 1.592.4 \
        --uk-version 2.75.1 \
        --environment staging
"""

import argparse

import modal


def update_version_dict(
    dict_name: str,
    environment: str,
    version: str,
    app_name: str,
) -> None:
    """Update a version dict entry, showing previous value if overwriting.

    Args:
        dict_name: Name of the Modal Dict (e.g., "simulation-api-us-versions")
        environment: Modal environment (staging or main)
        version: Package version (e.g., "1.592.4")
        app_name: App name to map this version to
    """
    version_dict = modal.Dict.from_name(
        dict_name,
        environment_name=environment,
        create_if_missing=True,
    )

    # Check for existing entry
    try:
        previous_app = version_dict[version]
        if previous_app != app_name:
            print(f"  {dict_name}[{version}]: {previous_app} -> {app_name}")
        else:
            print(f"  {dict_name}[{version}]: {app_name} (unchanged)")
    except KeyError:
        print(f"  {dict_name}[{version}]: (new) -> {app_name}")

    # Update entry
    version_dict[version] = app_name

    # Update latest pointer
    previous_latest = version_dict.get("latest")
    version_dict["latest"] = version
    if previous_latest != version:
        print(f"  {dict_name}[latest]: {previous_latest} -> {version}")
    else:
        print(f"  {dict_name}[latest]: {version} (unchanged)")


def main():
    parser = argparse.ArgumentParser(
        description="Update version registries after Modal deployment"
    )
    parser.add_argument(
        "--app-name",
        required=True,
        help="Versioned app name (e.g., policyengine-us1-592-4-uk2-75-1)",
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

    print(
        f"Updating version registries in Modal environment: {args.environment}"
    )
    print(f"  App name: {args.app_name}")
    print(f"  US version: {args.us_version}")
    print(f"  UK version: {args.uk_version}")
    print()

    print("US version registry:")
    update_version_dict(
        "simulation-api-us-versions",
        args.environment,
        args.us_version,
        args.app_name,
    )
    print()

    print("UK version registry:")
    update_version_dict(
        "simulation-api-uk-versions",
        args.environment,
        args.uk_version,
        args.app_name,
    )
    print()

    print("Version registries updated successfully.")


if __name__ == "__main__":
    main()
