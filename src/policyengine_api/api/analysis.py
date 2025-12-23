"""Economic impact and household analysis endpoints.

Use these endpoints to analyse policy effects at both household and population levels.

HOUSEHOLD-LEVEL ANALYSIS:
- /analysis/marginal-rate: Compute effective marginal tax rate for a household
- /analysis/budget-constraint: Compute net income across income range
- /analysis/cliffs: Identify benefit cliffs and high marginal rate regions
- /analysis/compare-policies: Compare multiple policy reforms for a household

ECONOMY-WIDE ANALYSIS:
- /analysis/economic-impact: Compare baseline vs reform across population dataset
  This is async - poll until status="completed" to get results

WORKFLOW for economic analysis:
1. Create a policy with parameter changes: POST /policies
2. Get a dataset: GET /datasets (look for UK/US datasets)
3. Start analysis: POST /analysis/economic-impact with policy_id and dataset_id
4. Check status: GET /analysis/economic-impact/{report_id} until status="completed"
5. Review results: The response includes decile_impacts and program_statistics
"""

import math
from typing import Any, Literal
from uuid import UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select


def _safe_float(value: float | None) -> float | None:
    """Convert NaN/inf to None for JSON serialization."""
    if value is None:
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return value


from policyengine_api.models import (
    Dataset,
    DecileImpact,
    DecileImpactRead,
    ProgramStatistics,
    ProgramStatisticsRead,
    Report,
    ReportStatus,
    Simulation,
    SimulationStatus,
    TaxBenefitModel,
    TaxBenefitModelVersion,
)
from policyengine_api.services.database import get_session

# Namespace for deterministic UUIDs
SIMULATION_NAMESPACE = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
REPORT_NAMESPACE = UUID("b2c3d4e5-f6a7-8901-bcde-f12345678901")

router = APIRouter(prefix="/analysis", tags=["analysis"])


class EconomicImpactRequest(BaseModel):
    """Request body for economic impact analysis.

    Example:
    {
        "tax_benefit_model_name": "policyengine_uk",
        "dataset_id": "uuid-from-datasets-endpoint",
        "policy_id": "uuid-of-reform-policy"
    }
    """

    tax_benefit_model_name: Literal["policyengine_uk", "policyengine_us"] = Field(
        description="Which country model to use"
    )
    dataset_id: UUID = Field(
        description="Dataset ID from /datasets endpoint containing population microdata"
    )
    policy_id: UUID | None = Field(
        default=None,
        description="Reform policy ID to compare against baseline (current law)",
    )
    dynamic_id: UUID | None = Field(
        default=None, description="Optional behavioural response specification ID"
    )


class SimulationInfo(BaseModel):
    """Simulation status info."""

    id: UUID
    status: SimulationStatus
    error_message: str | None = None


class EconomicImpactResponse(BaseModel):
    """Response from economic impact analysis."""

    report_id: UUID
    status: ReportStatus
    baseline_simulation: SimulationInfo
    reform_simulation: SimulationInfo
    error_message: str | None = None
    decile_impacts: list[DecileImpactRead] | None = None
    program_statistics: list[ProgramStatisticsRead] | None = None


def _get_model_version(
    tax_benefit_model_name: str, session: Session
) -> TaxBenefitModelVersion:
    """Get the latest tax benefit model version."""
    model_name = tax_benefit_model_name.replace("_", "-")

    model = session.exec(
        select(TaxBenefitModel).where(TaxBenefitModel.name == model_name)
    ).first()
    if not model:
        raise HTTPException(
            status_code=404, detail=f"Tax benefit model {model_name} not found"
        )

    version = session.exec(
        select(TaxBenefitModelVersion)
        .where(TaxBenefitModelVersion.model_id == model.id)
        .order_by(TaxBenefitModelVersion.created_at.desc())
    ).first()
    if not version:
        raise HTTPException(
            status_code=404, detail=f"No version found for model {model_name}"
        )

    return version


def _get_deterministic_simulation_id(
    dataset_id: UUID,
    model_version_id: UUID,
    policy_id: UUID | None,
    dynamic_id: UUID | None,
) -> UUID:
    """Generate a deterministic UUID from simulation parameters."""
    key = f"{dataset_id}:{model_version_id}:{policy_id}:{dynamic_id}"
    return uuid5(SIMULATION_NAMESPACE, key)


def _get_deterministic_report_id(
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
) -> UUID:
    """Generate a deterministic UUID from report parameters."""
    key = f"{baseline_sim_id}:{reform_sim_id}"
    return uuid5(REPORT_NAMESPACE, key)


def _get_or_create_simulation(
    dataset_id: UUID,
    model_version_id: UUID,
    policy_id: UUID | None,
    dynamic_id: UUID | None,
    session: Session,
) -> Simulation:
    """Get existing simulation or create a new one."""
    sim_id = _get_deterministic_simulation_id(
        dataset_id, model_version_id, policy_id, dynamic_id
    )

    existing = session.get(Simulation, sim_id)
    if existing:
        return existing

    simulation = Simulation(
        id=sim_id,
        dataset_id=dataset_id,
        tax_benefit_model_version_id=model_version_id,
        policy_id=policy_id,
        dynamic_id=dynamic_id,
        status=SimulationStatus.PENDING,
    )
    session.add(simulation)
    session.commit()
    session.refresh(simulation)
    return simulation


def _get_or_create_report(
    baseline_sim_id: UUID,
    reform_sim_id: UUID,
    label: str,
    session: Session,
) -> Report:
    """Get existing report or create a new one."""
    report_id = _get_deterministic_report_id(baseline_sim_id, reform_sim_id)

    existing = session.get(Report, report_id)
    if existing:
        return existing

    report = Report(
        id=report_id,
        label=label,
        baseline_simulation_id=baseline_sim_id,
        reform_simulation_id=reform_sim_id,
        status=ReportStatus.PENDING,
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return report


def _build_response(
    report: Report,
    baseline_sim: Simulation,
    reform_sim: Simulation,
    session: Session,
) -> EconomicImpactResponse:
    """Build response from report and simulations."""
    decile_impacts = None
    program_statistics = None

    if report.status == ReportStatus.COMPLETED:
        # Fetch decile impacts for this report
        deciles = session.exec(
            select(DecileImpact).where(DecileImpact.report_id == report.id)
        ).all()
        decile_impacts = [
            DecileImpactRead(
                id=d.id,
                created_at=d.created_at,
                baseline_simulation_id=d.baseline_simulation_id,
                reform_simulation_id=d.reform_simulation_id,
                report_id=d.report_id,
                income_variable=d.income_variable,
                entity=d.entity,
                decile=d.decile,
                quantiles=d.quantiles,
                baseline_mean=_safe_float(d.baseline_mean),
                reform_mean=_safe_float(d.reform_mean),
                absolute_change=_safe_float(d.absolute_change),
                relative_change=_safe_float(d.relative_change),
                count_better_off=_safe_float(d.count_better_off),
                count_worse_off=_safe_float(d.count_worse_off),
                count_no_change=_safe_float(d.count_no_change),
            )
            for d in deciles
        ]

        # Fetch program statistics for this report
        stats = session.exec(
            select(ProgramStatistics).where(ProgramStatistics.report_id == report.id)
        ).all()
        program_statistics = [
            ProgramStatisticsRead(
                id=s.id,
                created_at=s.created_at,
                baseline_simulation_id=s.baseline_simulation_id,
                reform_simulation_id=s.reform_simulation_id,
                report_id=s.report_id,
                program_name=s.program_name,
                entity=s.entity,
                is_tax=s.is_tax,
                baseline_total=_safe_float(s.baseline_total),
                reform_total=_safe_float(s.reform_total),
                change=_safe_float(s.change),
                baseline_count=_safe_float(s.baseline_count),
                reform_count=_safe_float(s.reform_count),
                winners=_safe_float(s.winners),
                losers=_safe_float(s.losers),
            )
            for s in stats
        ]

    return EconomicImpactResponse(
        report_id=report.id,
        status=report.status,
        baseline_simulation=SimulationInfo(
            id=baseline_sim.id,
            status=baseline_sim.status,
            error_message=baseline_sim.error_message,
        ),
        reform_simulation=SimulationInfo(
            id=reform_sim.id,
            status=reform_sim.status,
            error_message=reform_sim.error_message,
        ),
        error_message=report.error_message,
        decile_impacts=decile_impacts,
        program_statistics=program_statistics,
    )


@router.post("/economic-impact", response_model=EconomicImpactResponse)
def economic_impact(
    request: EconomicImpactRequest,
    session: Session = Depends(get_session),
) -> EconomicImpactResponse:
    """Run economy-wide impact analysis comparing baseline vs reform.

    This is an async operation. The endpoint returns immediately with a report_id
    and status="pending". Poll GET /analysis/economic-impact/{report_id} until
    status="completed" to get results.

    Results include decile impacts (income changes by income group) and
    program statistics (budgetary effects of tax/benefit programs).
    """
    # Validate dataset exists
    dataset = session.get(Dataset, request.dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=404, detail=f"Dataset {request.dataset_id} not found"
        )

    # Get model version
    model_version = _get_model_version(request.tax_benefit_model_name, session)

    # Get or create simulations
    baseline_sim = _get_or_create_simulation(
        dataset_id=request.dataset_id,
        model_version_id=model_version.id,
        policy_id=None,
        dynamic_id=request.dynamic_id,
        session=session,
    )

    reform_sim = _get_or_create_simulation(
        dataset_id=request.dataset_id,
        model_version_id=model_version.id,
        policy_id=request.policy_id,
        dynamic_id=request.dynamic_id,
        session=session,
    )

    # Get or create report
    label = f"Economic impact: {request.tax_benefit_model_name}"
    if request.policy_id:
        label += f" (policy {request.policy_id})"

    report = _get_or_create_report(baseline_sim.id, reform_sim.id, label, session)

    return _build_response(report, baseline_sim, reform_sim, session)


@router.get("/economic-impact/{report_id}", response_model=EconomicImpactResponse)
def get_economic_impact_status(
    report_id: UUID,
    session: Session = Depends(get_session),
) -> EconomicImpactResponse:
    """Get status and results of economic impact analysis."""
    report = session.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

    if not report.baseline_simulation_id or not report.reform_simulation_id:
        raise HTTPException(status_code=500, detail="Report missing simulation IDs")

    baseline_sim = session.get(Simulation, report.baseline_simulation_id)
    reform_sim = session.get(Simulation, report.reform_simulation_id)

    if not baseline_sim or not reform_sim:
        raise HTTPException(status_code=500, detail="Simulation data missing")

    return _build_response(report, baseline_sim, reform_sim, session)


# ============================================================================
# Household-level analysis endpoints
# ============================================================================


class MarginalRateRequest(BaseModel):
    """Request for marginal rate analysis.

    Computes effective marginal tax rate by calculating net income
    at base income and base income + delta, then computing the
    marginal rate as 1 - (change in net income / delta).
    """

    tax_benefit_model_name: Literal["policyengine_uk", "policyengine_us"] = Field(
        description="Which country model to use"
    )
    people: list[dict[str, Any]] = Field(
        description="List of people with flat variable values"
    )
    benunit: dict[str, Any] = Field(default_factory=dict)
    marital_unit: dict[str, Any] = Field(default_factory=dict)
    family: dict[str, Any] = Field(default_factory=dict)
    spm_unit: dict[str, Any] = Field(default_factory=dict)
    tax_unit: dict[str, Any] = Field(default_factory=dict)
    household: dict[str, Any] = Field(default_factory=dict)
    year: int | None = Field(default=None)
    policy_id: UUID | None = Field(default=None)
    dynamic_id: UUID | None = Field(default=None)
    person_index: int = Field(
        default=0,
        description="Index of person to vary income for (0-indexed)",
    )
    income_variable: str = Field(
        default="employment_income",
        description="Which income variable to vary",
    )
    delta: float = Field(
        default=1.0,
        description="Amount to increase income by (in currency units)",
    )
    net_income_variable: str = Field(
        default="household_net_income",
        description="Variable to use for net income calculation",
    )


class MarginalRateResponse(BaseModel):
    """Response from marginal rate analysis."""

    base_net_income: float
    incremented_net_income: float
    delta: float
    marginal_rate: float = Field(
        description="Effective marginal tax rate (1 - change in net income / delta)"
    )
    person_index: int
    income_variable: str


@router.post("/marginal-rate", response_model=MarginalRateResponse)
def calculate_marginal_rate(
    request: MarginalRateRequest,
    session: Session = Depends(get_session),
) -> MarginalRateResponse:
    """Calculate effective marginal tax rate for a household.

    Computes the rate at which the next unit of income is taxed/withdrawn,
    accounting for both taxes and benefit withdrawals.

    Example: If £1 extra income results in £0.32 extra net income,
    the marginal rate is 68%.
    """
    import logfire

    from policyengine_api.api.household import (
        HouseholdCalculateRequest,
        _calculate_uk,
        _calculate_us,
        _get_pe_dynamic,
        _get_pe_policy,
    )

    with logfire.span(
        "calculate_marginal_rate",
        model=request.tax_benefit_model_name,
        person_index=request.person_index,
        delta=request.delta,
    ):
        # Validate person index
        if request.person_index >= len(request.people):
            raise HTTPException(
                status_code=400,
                detail=f"person_index {request.person_index} out of range "
                f"(have {len(request.people)} people)",
            )

        # Get current income value
        base_income = request.people[request.person_index].get(
            request.income_variable, 0
        )

        # Create base request
        base_request = HouseholdCalculateRequest(
            tax_benefit_model_name=request.tax_benefit_model_name,
            people=request.people,
            benunit=request.benunit,
            marital_unit=request.marital_unit,
            family=request.family,
            spm_unit=request.spm_unit,
            tax_unit=request.tax_unit,
            household=request.household,
            year=request.year,
            policy_id=request.policy_id,
            dynamic_id=request.dynamic_id,
        )

        # Load model and policy/dynamic
        with logfire.span("load_model"):
            if request.tax_benefit_model_name == "policyengine_uk":
                from policyengine.tax_benefit_models.uk import uk_latest

                pe_model_version = uk_latest
            else:
                from policyengine.tax_benefit_models.us import us_latest

                pe_model_version = us_latest

        policy = _get_pe_policy(request.policy_id, pe_model_version, session)
        dynamic = _get_pe_dynamic(request.dynamic_id, pe_model_version, session)

        # Calculate base scenario
        with logfire.span("calculate_base"):
            if request.tax_benefit_model_name == "policyengine_uk":
                base_result = _calculate_uk(base_request, policy, dynamic)
            else:
                base_result = _calculate_us(base_request, policy, dynamic)

        # Create incremented request
        incremented_people = [p.copy() for p in request.people]
        incremented_people[request.person_index][request.income_variable] = (
            base_income + request.delta
        )

        incremented_request = HouseholdCalculateRequest(
            tax_benefit_model_name=request.tax_benefit_model_name,
            people=incremented_people,
            benunit=request.benunit,
            marital_unit=request.marital_unit,
            family=request.family,
            spm_unit=request.spm_unit,
            tax_unit=request.tax_unit,
            household=request.household,
            year=request.year,
            policy_id=request.policy_id,
            dynamic_id=request.dynamic_id,
        )

        # Calculate incremented scenario
        with logfire.span("calculate_incremented"):
            if request.tax_benefit_model_name == "policyengine_uk":
                incremented_result = _calculate_uk(incremented_request, policy, dynamic)
            else:
                incremented_result = _calculate_us(incremented_request, policy, dynamic)

        # Extract net income from household
        base_net = base_result.household.get(request.net_income_variable, 0)
        incremented_net = incremented_result.household.get(
            request.net_income_variable, 0
        )

        # Calculate marginal rate
        change_in_net = incremented_net - base_net
        marginal_rate = 1 - (change_in_net / request.delta) if request.delta != 0 else 0

        return MarginalRateResponse(
            base_net_income=base_net,
            incremented_net_income=incremented_net,
            delta=request.delta,
            marginal_rate=marginal_rate,
            person_index=request.person_index,
            income_variable=request.income_variable,
        )


class BudgetConstraintRequest(BaseModel):
    """Request for budget constraint analysis.

    Computes net income across a range of gross income values
    to visualise the budget constraint (effective tax schedule).
    """

    tax_benefit_model_name: Literal["policyengine_uk", "policyengine_us"] = Field(
        description="Which country model to use"
    )
    people: list[dict[str, Any]] = Field(
        description="List of people with flat variable values"
    )
    benunit: dict[str, Any] = Field(default_factory=dict)
    marital_unit: dict[str, Any] = Field(default_factory=dict)
    family: dict[str, Any] = Field(default_factory=dict)
    spm_unit: dict[str, Any] = Field(default_factory=dict)
    tax_unit: dict[str, Any] = Field(default_factory=dict)
    household: dict[str, Any] = Field(default_factory=dict)
    year: int | None = Field(default=None)
    policy_id: UUID | None = Field(default=None)
    dynamic_id: UUID | None = Field(default=None)
    person_index: int = Field(default=0)
    income_variable: str = Field(default="employment_income")
    net_income_variable: str = Field(default="household_net_income")
    min_income: float = Field(default=0, description="Minimum income to compute")
    max_income: float = Field(default=100000, description="Maximum income to compute")
    step: float = Field(default=1000, description="Income step size")


class BudgetConstraintPoint(BaseModel):
    """Single point on budget constraint."""

    gross_income: float
    net_income: float
    marginal_rate: float | None = None


class BudgetConstraintResponse(BaseModel):
    """Response from budget constraint analysis."""

    points: list[BudgetConstraintPoint]
    person_index: int
    income_variable: str
    net_income_variable: str


@router.post("/budget-constraint", response_model=BudgetConstraintResponse)
def calculate_budget_constraint(
    request: BudgetConstraintRequest,
    session: Session = Depends(get_session),
) -> BudgetConstraintResponse:
    """Calculate budget constraint across income range.

    Returns net income for each gross income level, useful for
    visualising effective tax schedules and identifying cliffs.
    """
    import logfire

    from policyengine_api.api.household import (
        HouseholdCalculateRequest,
        _calculate_uk,
        _calculate_us,
        _get_pe_dynamic,
        _get_pe_policy,
    )

    with logfire.span(
        "calculate_budget_constraint",
        model=request.tax_benefit_model_name,
        min_income=request.min_income,
        max_income=request.max_income,
        step=request.step,
    ):
        # Validate person index
        if request.person_index >= len(request.people):
            raise HTTPException(
                status_code=400,
                detail=f"person_index {request.person_index} out of range",
            )

        # Load model
        with logfire.span("load_model"):
            if request.tax_benefit_model_name == "policyengine_uk":
                from policyengine.tax_benefit_models.uk import uk_latest

                pe_model_version = uk_latest
            else:
                from policyengine.tax_benefit_models.us import us_latest

                pe_model_version = us_latest

        policy = _get_pe_policy(request.policy_id, pe_model_version, session)
        dynamic = _get_pe_dynamic(request.dynamic_id, pe_model_version, session)

        points = []
        prev_net = None

        income = request.min_income
        while income <= request.max_income:
            with logfire.span("calculate_point", income=income):
                # Create request for this income level
                people_copy = [p.copy() for p in request.people]
                people_copy[request.person_index][request.income_variable] = income

                calc_request = HouseholdCalculateRequest(
                    tax_benefit_model_name=request.tax_benefit_model_name,
                    people=people_copy,
                    benunit=request.benunit,
                    marital_unit=request.marital_unit,
                    family=request.family,
                    spm_unit=request.spm_unit,
                    tax_unit=request.tax_unit,
                    household=request.household,
                    year=request.year,
                    policy_id=request.policy_id,
                    dynamic_id=request.dynamic_id,
                )

                if request.tax_benefit_model_name == "policyengine_uk":
                    result = _calculate_uk(calc_request, policy, dynamic)
                else:
                    result = _calculate_us(calc_request, policy, dynamic)

                net_income = result.household.get(request.net_income_variable, 0)

                # Calculate marginal rate from previous point
                marginal_rate = None
                if prev_net is not None and request.step > 0:
                    change_in_net = net_income - prev_net
                    marginal_rate = 1 - (change_in_net / request.step)

                points.append(
                    BudgetConstraintPoint(
                        gross_income=income,
                        net_income=net_income,
                        marginal_rate=marginal_rate,
                    )
                )

                prev_net = net_income
                income += request.step

        return BudgetConstraintResponse(
            points=points,
            person_index=request.person_index,
            income_variable=request.income_variable,
            net_income_variable=request.net_income_variable,
        )


class CliffAnalysisRequest(BaseModel):
    """Request for cliff analysis.

    Identifies income ranges where marginal rates exceed a threshold,
    indicating benefit cliffs or phase-out regions.
    """

    tax_benefit_model_name: Literal["policyengine_uk", "policyengine_us"] = Field(
        description="Which country model to use"
    )
    people: list[dict[str, Any]] = Field(
        description="List of people with flat variable values"
    )
    benunit: dict[str, Any] = Field(default_factory=dict)
    marital_unit: dict[str, Any] = Field(default_factory=dict)
    family: dict[str, Any] = Field(default_factory=dict)
    spm_unit: dict[str, Any] = Field(default_factory=dict)
    tax_unit: dict[str, Any] = Field(default_factory=dict)
    household: dict[str, Any] = Field(default_factory=dict)
    year: int | None = Field(default=None)
    policy_id: UUID | None = Field(default=None)
    person_index: int = Field(default=0)
    income_variable: str = Field(default="employment_income")
    net_income_variable: str = Field(default="household_net_income")
    min_income: float = Field(default=0)
    max_income: float = Field(default=100000)
    step: float = Field(default=500)
    cliff_threshold: float = Field(
        default=0.7,
        description="Marginal rate threshold to consider a cliff (0.7 = 70%)",
    )


class CliffRegion(BaseModel):
    """A region where marginal rate exceeds threshold."""

    start_income: float
    end_income: float
    peak_marginal_rate: float
    avg_marginal_rate: float


class CliffAnalysisResponse(BaseModel):
    """Response from cliff analysis."""

    cliff_regions: list[CliffRegion]
    max_marginal_rate: float
    avg_marginal_rate: float
    cliff_threshold: float


@router.post("/cliffs", response_model=CliffAnalysisResponse)
def analyse_cliffs(
    request: CliffAnalysisRequest,
    session: Session = Depends(get_session),
) -> CliffAnalysisResponse:
    """Identify benefit cliffs and high marginal rate regions.

    Scans income range to find regions where marginal rates
    exceed the specified threshold, indicating cliffs or
    aggressive phase-outs.
    """
    import logfire

    with logfire.span(
        "analyse_cliffs",
        model=request.tax_benefit_model_name,
        threshold=request.cliff_threshold,
    ):
        # First get budget constraint
        bc_request = BudgetConstraintRequest(
            tax_benefit_model_name=request.tax_benefit_model_name,
            people=request.people,
            benunit=request.benunit,
            marital_unit=request.marital_unit,
            family=request.family,
            spm_unit=request.spm_unit,
            tax_unit=request.tax_unit,
            household=request.household,
            year=request.year,
            policy_id=request.policy_id,
            person_index=request.person_index,
            income_variable=request.income_variable,
            net_income_variable=request.net_income_variable,
            min_income=request.min_income,
            max_income=request.max_income,
            step=request.step,
        )

        bc_result = calculate_budget_constraint(bc_request, session)

        # Identify cliff regions
        cliff_regions = []
        current_cliff_start = None
        current_cliff_rates: list[float] = []

        all_rates: list[float] = []

        for point in bc_result.points:
            if point.marginal_rate is not None:
                all_rates.append(point.marginal_rate)

                if point.marginal_rate >= request.cliff_threshold:
                    if current_cliff_start is None:
                        current_cliff_start = point.gross_income - request.step
                    current_cliff_rates.append(point.marginal_rate)
                else:
                    if current_cliff_start is not None:
                        cliff_regions.append(
                            CliffRegion(
                                start_income=current_cliff_start,
                                end_income=point.gross_income - request.step,
                                peak_marginal_rate=max(current_cliff_rates),
                                avg_marginal_rate=sum(current_cliff_rates)
                                / len(current_cliff_rates),
                            )
                        )
                        current_cliff_start = None
                        current_cliff_rates = []

        # Handle cliff that extends to end
        if current_cliff_start is not None:
            avg_rate = sum(current_cliff_rates) / len(current_cliff_rates)
            cliff_regions.append(
                CliffRegion(
                    start_income=current_cliff_start,
                    end_income=request.max_income,
                    peak_marginal_rate=max(current_cliff_rates),
                    avg_marginal_rate=avg_rate,
                )
            )

        return CliffAnalysisResponse(
            cliff_regions=cliff_regions,
            max_marginal_rate=max(all_rates) if all_rates else 0,
            avg_marginal_rate=sum(all_rates) / len(all_rates) if all_rates else 0,
            cliff_threshold=request.cliff_threshold,
        )


class MultiPolicyCompareRequest(BaseModel):
    """Request for multi-policy comparison.

    Compares a household under baseline and multiple reform policies.
    """

    tax_benefit_model_name: Literal["policyengine_uk", "policyengine_us"] = Field(
        description="Which country model to use"
    )
    people: list[dict[str, Any]] = Field(
        description="List of people with flat variable values"
    )
    benunit: dict[str, Any] = Field(default_factory=dict)
    marital_unit: dict[str, Any] = Field(default_factory=dict)
    family: dict[str, Any] = Field(default_factory=dict)
    spm_unit: dict[str, Any] = Field(default_factory=dict)
    tax_unit: dict[str, Any] = Field(default_factory=dict)
    household: dict[str, Any] = Field(default_factory=dict)
    year: int | None = Field(default=None)
    policy_ids: list[UUID] = Field(
        description="List of policy IDs to compare (in addition to baseline)"
    )


class PolicyResult(BaseModel):
    """Result for a single policy."""

    policy_id: UUID | None
    policy_name: str
    household: dict[str, Any]
    person: list[dict[str, Any]]


class MultiPolicyCompareResponse(BaseModel):
    """Response from multi-policy comparison."""

    baseline: PolicyResult
    reforms: list[PolicyResult]
    summary: dict[str, Any] = Field(
        description="Summary of key differences across policies"
    )


@router.post("/compare-policies", response_model=MultiPolicyCompareResponse)
def compare_multiple_policies(
    request: MultiPolicyCompareRequest,
    session: Session = Depends(get_session),
) -> MultiPolicyCompareResponse:
    """Compare a household under baseline and multiple reform policies.

    Useful for evaluating alternative policy proposals side-by-side.
    """
    import logfire

    from policyengine_api.api.household import (
        HouseholdCalculateRequest,
        _calculate_uk,
        _calculate_us,
        _get_pe_policy,
    )
    from policyengine_api.models import Policy

    with logfire.span(
        "compare_multiple_policies",
        model=request.tax_benefit_model_name,
        num_policies=len(request.policy_ids),
    ):
        # Load model
        with logfire.span("load_model"):
            if request.tax_benefit_model_name == "policyengine_uk":
                from policyengine.tax_benefit_models.uk import uk_latest

                pe_model_version = uk_latest
            else:
                from policyengine.tax_benefit_models.us import us_latest

                pe_model_version = us_latest

        # Calculate baseline
        with logfire.span("calculate_baseline"):
            base_request = HouseholdCalculateRequest(
                tax_benefit_model_name=request.tax_benefit_model_name,
                people=request.people,
                benunit=request.benunit,
                marital_unit=request.marital_unit,
                family=request.family,
                spm_unit=request.spm_unit,
                tax_unit=request.tax_unit,
                household=request.household,
                year=request.year,
            )

            if request.tax_benefit_model_name == "policyengine_uk":
                baseline_result = _calculate_uk(base_request, None, None)
            else:
                baseline_result = _calculate_us(base_request, None, None)

        baseline = PolicyResult(
            policy_id=None,
            policy_name="Baseline (current law)",
            household=baseline_result.household,
            person=baseline_result.person,
        )

        # Calculate each reform
        reforms = []
        for policy_id in request.policy_ids:
            with logfire.span("calculate_reform", policy_id=str(policy_id)):
                db_policy = session.get(Policy, policy_id)
                if not db_policy:
                    raise HTTPException(
                        status_code=404, detail=f"Policy {policy_id} not found"
                    )

                policy = _get_pe_policy(policy_id, pe_model_version, session)

                reform_request = HouseholdCalculateRequest(
                    tax_benefit_model_name=request.tax_benefit_model_name,
                    people=request.people,
                    benunit=request.benunit,
                    marital_unit=request.marital_unit,
                    family=request.family,
                    spm_unit=request.spm_unit,
                    tax_unit=request.tax_unit,
                    household=request.household,
                    year=request.year,
                    policy_id=policy_id,
                )

                if request.tax_benefit_model_name == "policyengine_uk":
                    reform_result = _calculate_uk(reform_request, policy, None)
                else:
                    reform_result = _calculate_us(reform_request, policy, None)

                reforms.append(
                    PolicyResult(
                        policy_id=policy_id,
                        policy_name=db_policy.name,
                        household=reform_result.household,
                        person=reform_result.person,
                    )
                )

        # Build summary comparing key variables
        summary: dict[str, Any] = {
            "net_income": {
                "baseline": baseline.household.get("household_net_income", 0),
            }
        }
        for reform in reforms:
            summary["net_income"][reform.policy_name] = reform.household.get(
                "household_net_income", 0
            )

        return MultiPolicyCompareResponse(
            baseline=baseline,
            reforms=reforms,
            summary=summary,
        )
