"""Helpers for resolving the deployed PolicyEngine runtime bundle."""

from importlib import import_module
from uuid import UUID

from sqlmodel import Session


def _normalize_model_name(model_name: str) -> str:
    return model_name.replace("_", "-").lower()


def _load_runtime_model_version(model_name: str):
    normalized_name = _normalize_model_name(model_name)

    if normalized_name == "policyengine-uk":
        return import_module("policyengine.tax_benefit_models.uk").uk_latest
    if normalized_name == "policyengine-us":
        return import_module("policyengine.tax_benefit_models.us").us_latest

    raise ValueError(f"Unsupported tax-benefit model '{model_name}'")


def resolve_runtime_model_version_from_db(
    session: Session,
    tax_benefit_model_version_id: UUID,
):
    """Resolve the deployed policyengine model version for a stored DB row.

    The current deployment only has one runtime bundle per country. If the
    stored DB version does not match the deployed runtime bundle, fail clearly
    instead of silently executing against `*_latest`.
    """
    from policyengine_api.models import TaxBenefitModel, TaxBenefitModelVersion

    db_version = session.get(TaxBenefitModelVersion, tax_benefit_model_version_id)
    if db_version is None:
        raise ValueError(
            f"Tax-benefit model version {tax_benefit_model_version_id} not found"
        )

    db_model = session.get(TaxBenefitModel, db_version.model_id)
    if db_model is None:
        raise ValueError(f"Tax-benefit model {db_version.model_id} not found")

    runtime_model_version = _load_runtime_model_version(db_model.name)
    runtime_version = getattr(runtime_model_version, "version", None)

    if runtime_version != db_version.version:
        raise ValueError(
            "Stored tax-benefit model version "
            f"{db_model.name}@{db_version.version} does not match the deployed "
            f"runtime bundle {db_model.name}@{runtime_version}. "
            "Re-seed this environment with the deployed bundle or re-run the "
            "analysis against the currently deployed version."
        )

    return runtime_model_version


def resolve_shared_runtime_model_version_from_db(
    session: Session,
    *tax_benefit_model_version_ids: UUID,
):
    """Resolve one deployed runtime model version shared across DB version rows."""
    if not tax_benefit_model_version_ids:
        raise ValueError("At least one tax-benefit model version ID is required")

    resolved_versions = [
        resolve_runtime_model_version_from_db(session, version_id)
        for version_id in tax_benefit_model_version_ids
    ]
    first_version = resolved_versions[0]

    for runtime_model_version in resolved_versions[1:]:
        if runtime_model_version.version != first_version.version:
            raise ValueError(
                "All simulations in a comparison must use the same deployed "
                f"runtime bundle. Got {first_version.version} and "
                f"{runtime_model_version.version}."
            )

    return first_version
