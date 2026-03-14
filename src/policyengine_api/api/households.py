"""Stored household CRUD endpoints.

Households represent saved household definitions that can be reused across
calculations and impact analyses. Create a household once, then reference
it by ID for repeated simulations.

These endpoints manage stored household *definitions* (people, entity groups,
model name, year). For running calculations on a household, use the
/household/calculate and /household/impact endpoints instead.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from policyengine_api.models import Household, HouseholdCreate, HouseholdRead
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/households", tags=["households"])

_ENTITY_GROUP_KEYS = (
    "tax_unit",
    "family",
    "spm_unit",
    "marital_unit",
    "household",
    "benunit",
)


def _pack_household_data(body: HouseholdCreate) -> dict[str, Any]:
    """Pack the flat request fields into a single JSON blob for storage."""
    data: dict[str, Any] = {"people": body.people}
    for key in _ENTITY_GROUP_KEYS:
        val = getattr(body, key)
        if val is not None:
            data[key] = val
    return data


def _to_read(record: Household) -> HouseholdRead:
    """Unpack the JSON blob back into the flat response shape."""
    data = record.household_data
    return HouseholdRead(
        id=record.id,
        country_id=record.country_id,
        year=record.year,
        label=record.label,
        people=data["people"],
        tax_unit=data.get("tax_unit"),
        family=data.get("family"),
        spm_unit=data.get("spm_unit"),
        marital_unit=data.get("marital_unit"),
        household=data.get("household"),
        benunit=data.get("benunit"),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.post("/", response_model=HouseholdRead, status_code=201)
def create_household(body: HouseholdCreate, session: Session = Depends(get_session)):
    """Create a stored household definition.

    The household data (people + entity groups) is persisted so it can be
    retrieved later by ID. Use the returned ID with /household/calculate
    or /household/impact to run simulations.
    """
    record = Household(
        country_id=body.country_id,
        year=body.year,
        label=body.label,
        household_data=_pack_household_data(body),
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return _to_read(record)


@router.get("/", response_model=list[HouseholdRead])
def list_households(
    country_id: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    """List stored households with optional filtering."""
    query = select(Household)
    if country_id is not None:
        query = query.where(Household.country_id == country_id)
    query = query.offset(offset).limit(limit)
    records = session.exec(query).all()
    return [_to_read(r) for r in records]


@router.get("/{household_id}", response_model=HouseholdRead)
def get_household(household_id: UUID, session: Session = Depends(get_session)):
    """Get a stored household by ID."""
    record = session.get(Household, household_id)
    if not record:
        raise HTTPException(
            status_code=404, detail=f"Household {household_id} not found"
        )
    return _to_read(record)


@router.delete("/{household_id}", status_code=204)
def delete_household(household_id: UUID, session: Session = Depends(get_session)):
    """Delete a stored household."""
    record = session.get(Household, household_id)
    if not record:
        raise HTTPException(
            status_code=404, detail=f"Household {household_id} not found"
        )
    session.delete(record)
    session.commit()
