"""Region endpoints for geographic areas used in analysis.

Regions represent geographic areas from countries down to states,
congressional districts, cities, etc. Each region has an associated
dataset for running simulations.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from policyengine_api.config.constants import CountryId
from policyengine_api.models import Region, RegionRead, TaxBenefitModel
from policyengine_api.services.database import get_session
from policyengine_api.services.model_resolver import resolve_model_name

router = APIRouter(prefix="/regions", tags=["regions"])


@router.get("/", response_model=List[RegionRead])
def list_regions(
    country_id: CountryId | None = Query(
        None, description="Filter by country ('us' or 'uk')"
    ),
    tax_benefit_model_id: UUID | None = Query(
        None, description="Filter by tax-benefit model ID"
    ),
    region_type: str | None = Query(
        None,
        description="Filter by region type (e.g., 'state', 'congressional_district')",
    ),
    session: Session = Depends(get_session),
):
    """List available regions.

    Returns regions that can be used with the /analysis/economic-impact endpoint.
    Each region represents a geographic area with an associated dataset.

    Args:
        country_id: Filter by country ("us" or "uk").
        tax_benefit_model_id: Filter by tax-benefit model UUID (alternative to country_id).
        region_type: Filter by region type (e.g., "state", "congressional_district").
    """
    query = select(Region)

    if country_id:
        model_name = resolve_model_name(country_id)
        query = query.join(TaxBenefitModel).where(
            TaxBenefitModel.name == model_name
        )
    elif tax_benefit_model_id:
        query = query.where(Region.tax_benefit_model_id == tax_benefit_model_id)

    if region_type:
        query = query.where(Region.region_type == region_type)

    regions = session.exec(query).all()
    return regions


@router.get("/{region_id}", response_model=RegionRead)
def get_region(region_id: UUID, session: Session = Depends(get_session)):
    """Get a specific region by ID."""
    region = session.get(Region, region_id)
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")
    return region


@router.get("/by-code/{region_code:path}", response_model=RegionRead)
def get_region_by_code(
    region_code: str,
    country_id: CountryId | None = Query(
        None, description="Filter by country ('us' or 'uk')"
    ),
    tax_benefit_model_id: UUID | None = Query(
        None,
        description="Tax-benefit model ID (alternative to country_id)",
    ),
    session: Session = Depends(get_session),
):
    """Get a specific region by code.

    Region codes use a prefix format like "state/ca" or "constituency/Sheffield Central".

    Args:
        region_code: The region code (e.g., "state/ca", "us").
        country_id: Filter by country ("us" or "uk").
        tax_benefit_model_id: Filter by tax-benefit model UUID (alternative to country_id).
    """
    query = select(Region).where(Region.code == region_code)

    if country_id:
        model_name = resolve_model_name(country_id)
        query = query.join(TaxBenefitModel).where(
            TaxBenefitModel.name == model_name
        )
    elif tax_benefit_model_id:
        query = query.where(Region.tax_benefit_model_id == tax_benefit_model_id)

    region = session.exec(query).first()
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")
    return region
