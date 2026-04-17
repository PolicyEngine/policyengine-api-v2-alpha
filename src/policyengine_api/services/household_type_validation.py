"""Validate household entity values against their declared variable dtypes.

The household endpoints build MicroDataFrames from raw user-supplied dicts
(see ``api/household.py`` and ``modal/functions/__init__.py``). If a user
submits a string where the variable metadata says ``float``, pandas silently
produces an object-dtype column and the downstream simulation raises a
hard-to-debug error or (worse) returns garbage.

This module looks up the country's variable catalog once, caches the
``(name → data_type)`` map, and validates each user-supplied value before it
is placed in ``person_data`` (or the equivalent per-entity dict). Type
mismatches raise ``HTTPException(422)`` so clients get a precise error.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from policyengine_api.config.constants import CountryId
from policyengine_api.models import Variable
from policyengine_api.services.model_resolver import resolve_country_model

# PolicyEngine's Variable.data_type is a string from the openfisca vocabulary
# (``"int"``, ``"float"``, ``"bool"``, ``"str"``, ``"Enum"``). Map each to
# the Python types we will accept at the API boundary.
_ALLOWED_TYPES: dict[str, tuple[type, ...]] = {
    "int": (int,),
    # bool is a subclass of int; we explicitly allow it for numeric columns
    # so ``{"is_married": True}`` keeps working.
    "float": (int, float, bool),
    "bool": (bool, int),
    "str": (str,),
    # Enums arrive as their string name (openfisca convention) and we never
    # have enough context at this layer to validate against the concrete
    # enum class, so we only enforce that the value is a string.
    "Enum": (str,),
}


def _variable_types_for_country(
    country_id: CountryId, session: Session
) -> dict[str, str]:
    """Return a ``{variable_name: data_type}`` map for the latest country model."""
    _, version = resolve_country_model(country_id, session)
    rows = session.exec(
        select(Variable.name, Variable.data_type).where(
            Variable.tax_benefit_model_version_id == version.id
        )
    ).all()
    return {name: dtype for name, dtype in rows if dtype}


def validate_entity_values(
    entity_name: str,
    entities: list[dict[str, Any]],
    types_by_name: dict[str, str],
) -> None:
    """Validate a list of entity dicts against their declared variable dtypes.

    Structural fields (``person_id``, ``person_benunit_id``, …) are skipped
    because they are not present in the variables catalog.
    """
    for idx, entity in enumerate(entities):
        if not isinstance(entity, dict):
            continue
        for key, value in entity.items():
            dtype = types_by_name.get(key)
            if dtype is None:
                # Unknown variable: leave validation to the simulation layer,
                # which already returns a legible error for typos.
                continue
            allowed = _ALLOWED_TYPES.get(dtype)
            if allowed is None:
                continue
            if value is None:
                continue
            if not isinstance(value, allowed):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"{entity_name}[{idx}].{key}: expected {dtype}, got "
                        f"{type(value).__name__} (value={value!r})"
                    ),
                )


def validate_household_payload(
    country_id: CountryId,
    session: Session,
    *,
    people: list[dict[str, Any]],
    benunit: list[dict[str, Any]] | None = None,
    marital_unit: list[dict[str, Any]] | None = None,
    family: list[dict[str, Any]] | None = None,
    spm_unit: list[dict[str, Any]] | None = None,
    tax_unit: list[dict[str, Any]] | None = None,
    household: list[dict[str, Any]] | None = None,
) -> None:
    """Validate all entity dicts for a household calculation request.

    Raises ``HTTPException(422)`` on the first type mismatch.
    """
    types_by_name = _variable_types_for_country(country_id, session)
    for name, entities in (
        ("people", people),
        ("benunit", benunit or []),
        ("marital_unit", marital_unit or []),
        ("family", family or []),
        ("spm_unit", spm_unit or []),
        ("tax_unit", tax_unit or []),
        ("household", household or []),
    ):
        validate_entity_values(name, entities, types_by_name)
