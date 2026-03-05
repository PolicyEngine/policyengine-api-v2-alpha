"""User-report association endpoints.

Associates users with reports they've created. This enables users to
maintain a list of their reports across sessions without duplicating
the underlying report data.

Note: user_id is a client-generated UUID (via crypto.randomUUID()) stored in
the browser's localStorage. It is NOT validated against a users table, allowing
anonymous users to save reports without authentication.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from policyengine_api.api.analysis import (
    EconomicImpactResponse,
    RegionInfo,
    SimulationInfo,
)
from policyengine_api.api.analysis import (
    _build_response as build_economic_response,
)
from policyengine_api.api.household_analysis import (
    HouseholdImpactResponse,
    build_household_response,
)
from policyengine_api.api.households import _to_read as household_to_read
from policyengine_api.api.policies import _policy_to_read
from policyengine_api.config.constants import CountryId
from policyengine_api.models import (
    Household,
    HouseholdRead,
    ParameterValue,
    Policy,
    PolicyRead,
    Region,
    Report,
    ReportRead,
    Simulation,
    UserReportAssociation,
    UserReportAssociationCreate,
    UserReportAssociationRead,
    UserReportAssociationUpdate,
)
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/user-reports", tags=["user-reports"])


@router.post("/", response_model=UserReportAssociationRead)
def create_user_report(
    body: UserReportAssociationCreate,
    session: Session = Depends(get_session),
):
    """Create a new user-report association.

    Associates a user with a report, allowing them to save it to their list.
    Duplicates are allowed - users can save the same report multiple times
    with different labels.
    """
    report = session.get(Report, body.report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    record = UserReportAssociation.model_validate(body)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@router.get("/", response_model=list[UserReportAssociationRead])
def list_user_reports(
    user_id: UUID = Query(..., description="User ID to filter by"),
    country_id: CountryId | None = Query(
        None, description="Filter by country ('us' or 'uk')"
    ),
    session: Session = Depends(get_session),
):
    """List all report associations for a user.

    Returns all reports saved by the specified user. Optionally filter by country.
    """
    query = select(UserReportAssociation).where(
        UserReportAssociation.user_id == user_id
    )

    if country_id:
        query = query.where(UserReportAssociation.country_id == country_id)

    return session.exec(query).all()


@router.get("/{user_report_id}", response_model=UserReportAssociationRead)
def get_user_report(
    user_report_id: UUID,
    session: Session = Depends(get_session),
):
    """Get a specific user-report association by ID."""
    record = session.get(UserReportAssociation, user_report_id)
    if not record:
        raise HTTPException(status_code=404, detail="User-report association not found")
    return record


@router.patch("/{user_report_id}", response_model=UserReportAssociationRead)
def update_user_report(
    user_report_id: UUID,
    updates: UserReportAssociationUpdate,
    user_id: UUID = Query(..., description="User ID for ownership verification"),
    session: Session = Depends(get_session),
):
    """Update a user-report association (e.g., rename label or update last_run_at).

    Requires user_id to verify ownership - only the owner can update.
    """
    record = session.exec(
        select(UserReportAssociation).where(
            UserReportAssociation.id == user_report_id,
            UserReportAssociation.user_id == user_id,
        )
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="User-report association not found")

    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(record, key, value)

    record.updated_at = datetime.now(timezone.utc)

    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@router.delete("/{user_report_id}", status_code=204)
def delete_user_report(
    user_report_id: UUID,
    user_id: UUID = Query(..., description="User ID for ownership verification"),
    session: Session = Depends(get_session),
):
    """Delete a user-report association.

    This only removes the association, not the underlying report.
    Requires user_id to verify ownership - only the owner can delete.
    """
    record = session.exec(
        select(UserReportAssociation).where(
            UserReportAssociation.id == user_report_id,
            UserReportAssociation.user_id == user_id,
        )
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="User-report association not found")

    session.delete(record)
    session.commit()


# ---------------------------------------------------------------------------
# GET /user-reports/{user_report_id}/full — read-only composite endpoint
# ---------------------------------------------------------------------------


class UserReportFullResponse(BaseModel):
    """Complete user-report data in a single response.

    Read-only: does NOT trigger computation. If the report hasn't been
    run yet, status will be "pending" and result fields will be null.
    """

    # Association metadata
    id: UUID
    user_id: UUID
    report_id: UUID
    country_id: str
    label: str | None
    created_at: datetime
    last_run_at: datetime | None

    # Report
    report: ReportRead

    # Simulations (metadata only)
    baseline_simulation: SimulationInfo | None = None
    reform_simulation: SimulationInfo | None = None

    # Policies with parameter values (null = current law)
    baseline_policy: PolicyRead | None = None
    reform_policy: PolicyRead | None = None

    # Population (household-type reports only)
    household: HouseholdRead | None = None

    # Region (economy-type reports only)
    region: RegionInfo | None = None

    # Results — one of these is populated when status == completed
    economic_impact: EconomicImpactResponse | None = None
    household_impact: HouseholdImpactResponse | None = None


@router.get("/{user_report_id}/full", response_model=UserReportFullResponse)
def get_user_report_full(
    user_report_id: UUID,
    session: Session = Depends(get_session),
):
    """Get complete user-report data in a single call.

    Assembles association metadata, report, simulations, policies (with
    parameter values), household/region, and results into one response.

    Read-only: does NOT trigger computation.
    """
    # 1. Load association
    record = session.get(UserReportAssociation, user_report_id)
    if not record:
        raise HTTPException(status_code=404, detail="User-report association not found")

    # 2. Load report
    report = session.get(Report, record.report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    report_read = ReportRead.model_validate(report)

    # 3. Load simulations
    baseline_sim = (
        session.get(Simulation, report.baseline_simulation_id)
        if report.baseline_simulation_id
        else None
    )
    reform_sim = (
        session.get(Simulation, report.reform_simulation_id)
        if report.reform_simulation_id
        else None
    )

    baseline_sim_info = (
        SimulationInfo(
            id=baseline_sim.id,
            status=baseline_sim.status,
            error_message=baseline_sim.error_message,
        )
        if baseline_sim
        else None
    )
    reform_sim_info = (
        SimulationInfo(
            id=reform_sim.id,
            status=reform_sim.status,
            error_message=reform_sim.error_message,
        )
        if reform_sim
        else None
    )

    # 4. Load policies with parameter values (eager-loaded)
    baseline_policy_read = _load_policy_read(
        baseline_sim.policy_id if baseline_sim else None, session
    )
    reform_policy_read = _load_policy_read(
        reform_sim.policy_id if reform_sim else None, session
    )

    # 5. Load household (for household-type reports)
    household_read = None
    if baseline_sim and baseline_sim.household_id:
        household = session.get(Household, baseline_sim.household_id)
        if household:
            household_read = household_to_read(household)

    # 6. Build region info (for economy-type reports)
    region_info = _build_region_info(baseline_sim, session)

    # 7. Build results
    economic_impact = None
    household_impact = None

    is_economy = report.report_type and "economy" in report.report_type
    is_household = report.report_type and "household" in report.report_type

    if is_economy and baseline_sim and reform_sim:
        # Look up region object for full response
        region_obj = (
            session.get(Region, baseline_sim.region_id)
            if baseline_sim.region_id
            else None
        )
        economic_impact = build_economic_response(
            report, baseline_sim, reform_sim, session, region_obj
        )
    elif is_household and baseline_sim:
        household_impact = build_household_response(
            report, baseline_sim, reform_sim, session
        )

    return UserReportFullResponse(
        id=record.id,
        user_id=record.user_id,
        report_id=record.report_id,
        country_id=record.country_id,
        label=record.label,
        created_at=record.created_at,
        last_run_at=record.last_run_at,
        report=report_read,
        baseline_simulation=baseline_sim_info,
        reform_simulation=reform_sim_info,
        baseline_policy=baseline_policy_read,
        reform_policy=reform_policy_read,
        household=household_read,
        region=region_info,
        economic_impact=economic_impact,
        household_impact=household_impact,
    )


def _load_policy_read(policy_id: UUID | None, session: Session) -> PolicyRead | None:
    """Load a policy with eager-loaded parameter values, or return None."""
    if not policy_id:
        return None

    query = (
        select(Policy)
        .where(Policy.id == policy_id)
        .options(
            selectinload(Policy.parameter_values).selectinload(ParameterValue.parameter)
        )
    )
    policy = session.exec(query).first()
    if not policy:
        return None

    return _policy_to_read(policy)


def _build_region_info(
    simulation: Simulation | None, session: Session
) -> RegionInfo | None:
    """Build RegionInfo from a simulation's region_id FK."""
    if not simulation or not simulation.region_id:
        return None

    region = session.get(Region, simulation.region_id)
    if not region:
        return None

    return RegionInfo(
        code=region.code,
        label=region.label,
        region_type=region.region_type,
        requires_filter=region.requires_filter,
        filter_field=region.filter_field,
        filter_value=region.filter_value,
    )


# ---------------------------------------------------------------------------
# GET /reports/{report_id}/full — report-level composite endpoint
# ---------------------------------------------------------------------------

reports_router = APIRouter(prefix="/reports", tags=["reports"])


class ReportFullResponse(BaseModel):
    """Complete report data in a single response.

    Read-only: does NOT trigger computation.
    Like UserReportFullResponse but keyed by report_id instead of
    user-report association ID.
    """

    # Report
    report: ReportRead

    # Simulations (metadata only)
    baseline_simulation: SimulationInfo | None = None
    reform_simulation: SimulationInfo | None = None

    # Policies with parameter values (null = current law)
    baseline_policy: PolicyRead | None = None
    reform_policy: PolicyRead | None = None

    # Population (household-type reports only)
    household: HouseholdRead | None = None

    # Region (economy-type reports only)
    region: RegionInfo | None = None

    # Results — one of these is populated when status == completed
    economic_impact: EconomicImpactResponse | None = None
    household_impact: HouseholdImpactResponse | None = None


@reports_router.get("/{report_id}/full", response_model=ReportFullResponse)
def get_report_full(
    report_id: UUID,
    session: Session = Depends(get_session),
):
    """Get complete report data in a single call.

    Assembles report, simulations, policies (with parameter values),
    household/region, and results into one response.

    Read-only: does NOT trigger computation.
    """
    report = session.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    report_read = ReportRead.model_validate(report)

    # Load simulations
    baseline_sim = (
        session.get(Simulation, report.baseline_simulation_id)
        if report.baseline_simulation_id
        else None
    )
    reform_sim = (
        session.get(Simulation, report.reform_simulation_id)
        if report.reform_simulation_id
        else None
    )

    baseline_sim_info = (
        SimulationInfo(
            id=baseline_sim.id,
            status=baseline_sim.status,
            error_message=baseline_sim.error_message,
        )
        if baseline_sim
        else None
    )
    reform_sim_info = (
        SimulationInfo(
            id=reform_sim.id,
            status=reform_sim.status,
            error_message=reform_sim.error_message,
        )
        if reform_sim
        else None
    )

    # Load policies with parameter values
    baseline_policy_read = _load_policy_read(
        baseline_sim.policy_id if baseline_sim else None, session
    )
    reform_policy_read = _load_policy_read(
        reform_sim.policy_id if reform_sim else None, session
    )

    # Load household (for household-type reports)
    household_read = None
    if baseline_sim and baseline_sim.household_id:
        household = session.get(Household, baseline_sim.household_id)
        if household:
            household_read = household_to_read(household)

    # Build region info (for economy-type reports)
    region_info = _build_region_info(baseline_sim, session)

    # Build results
    economic_impact = None
    household_impact = None

    is_economy = report.report_type and "economy" in report.report_type
    is_household = report.report_type and "household" in report.report_type

    if is_economy and baseline_sim and reform_sim:
        region_obj = (
            session.get(Region, baseline_sim.region_id)
            if baseline_sim.region_id
            else None
        )
        economic_impact = build_economic_response(
            report, baseline_sim, reform_sim, session, region_obj
        )
    elif is_household and baseline_sim:
        household_impact = build_household_response(
            report, baseline_sim, reform_sim, session
        )

    return ReportFullResponse(
        report=report_read,
        baseline_simulation=baseline_sim_info,
        reform_simulation=reform_sim_info,
        baseline_policy=baseline_policy_read,
        reform_policy=reform_policy_read,
        household=household_read,
        region=region_info,
        economic_impact=economic_impact,
        household_impact=household_impact,
    )
