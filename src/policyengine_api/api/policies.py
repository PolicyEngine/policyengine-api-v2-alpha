"""Policy reform endpoints.

Policies represent tax-benefit parameter reforms that can be compared against
baseline (current law). Create a policy, then use its ID with the household
calculation or economic impact endpoints to see the reform's effects.

WORKFLOW: To analyze a policy reform (e.g. lowering UK basic income tax rate to 16%):

1. Search for the parameter: GET /parameters?search=basic_rate
2. Note the parameter_id from the results
3. Create a policy with parameter values:
   POST /policies
   {
     "name": "Lower basic rate to 16p",
     "description": "Reduce UK basic income tax rate from 20p to 16p",
     "parameter_values": [
       {
         "parameter_id": "<uuid-from-step-1>",
         "value_json": 0.16,
         "start_date": "2026-01-01T00:00:00Z",
         "end_date": null
       }
     ]
   }
4. Test on a household: POST /household/impact with the policy_id
5. Run population analysis: POST /analysis/economic-impact with policy_id and dataset_id
6. Poll GET /analysis/economic-impact/{report_id} until status="completed"
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from policyengine_api.models import (
    Parameter,
    ParameterValue,
    ParameterValueWithName,
    Policy,
    PolicyCreate,
    PolicyRead,
    TaxBenefitModel,
)
from policyengine_api.services.database import get_session


def _policy_to_read(policy: Policy) -> PolicyRead:
    """Convert a Policy ORM object to PolicyRead with parameter names."""
    pv_with_names = []
    for pv in policy.parameter_values:
        pv_with_names.append(
            ParameterValueWithName(
                id=pv.id,
                parameter_id=pv.parameter_id,
                value_json=pv.value_json,
                start_date=pv.start_date,
                end_date=pv.end_date,
                policy_id=pv.policy_id,
                dynamic_id=pv.dynamic_id,
                created_at=pv.created_at,
                parameter_name=pv.parameter.name,
            )
        )
    return PolicyRead(
        id=policy.id,
        name=policy.name,
        description=policy.description,
        tax_benefit_model_id=policy.tax_benefit_model_id,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
        parameter_values=pv_with_names,
    )


router = APIRouter(prefix="/policies", tags=["policies"])


@router.post("/", response_model=PolicyRead)
def create_policy(policy: PolicyCreate, session: Session = Depends(get_session)):
    """Create a new policy reform with parameter values.

    Policies define changes to tax-benefit parameters. After creating a policy,
    use its ID with /household/calculate or /analysis/economic-impact to see effects.

    Include parameter_values in the request to specify which parameters to change:
    {
        "name": "Lower basic rate to 16p",
        "description": "Reduce UK basic income tax rate from 20p to 16p",
        "parameter_values": [
            {
                "parameter_id": "uuid-from-parameters-search",
                "value_json": 0.16,
                "start_date": "2026-01-01T00:00:00Z",
                "end_date": null
            }
        ]
    }
    """
    # Validate tax_benefit_model exists
    tax_model = session.get(TaxBenefitModel, policy.tax_benefit_model_id)
    if not tax_model:
        raise HTTPException(status_code=404, detail="Tax benefit model not found")

    # Create the policy
    db_policy = Policy(
        name=policy.name,
        description=policy.description,
        tax_benefit_model_id=policy.tax_benefit_model_id,
    )
    session.add(db_policy)
    session.flush()  # Get the policy ID before adding parameter values

    # Create associated parameter values
    for pv_data in policy.parameter_values:
        # Validate parameter exists
        param = session.get(Parameter, pv_data.parameter_id)
        if not param:
            raise HTTPException(
                status_code=404,
                detail=f"Parameter {pv_data.parameter_id} not found",
            )

        # Create parameter value (dates already parsed by Pydantic)
        db_pv = ParameterValue(
            parameter_id=pv_data.parameter_id,
            value_json=pv_data.value_json,
            start_date=pv_data.start_date,
            end_date=pv_data.end_date,
            policy_id=db_policy.id,
        )
        session.add(db_pv)

    session.commit()

    # Re-fetch with eager loading for the response
    query = (
        select(Policy)
        .where(Policy.id == db_policy.id)
        .options(
            selectinload(Policy.parameter_values).selectinload(ParameterValue.parameter)
        )
    )
    db_policy = session.exec(query).one()
    return _policy_to_read(db_policy)


@router.get("/", response_model=List[PolicyRead])
def list_policies(
    tax_benefit_model_id: UUID | None = Query(
        None, description="Filter by tax benefit model"
    ),
    session: Session = Depends(get_session),
):
    """List all policies, optionally filtered by tax benefit model."""
    query = select(Policy).options(
        selectinload(Policy.parameter_values).selectinload(ParameterValue.parameter)
    )
    if tax_benefit_model_id:
        query = query.where(Policy.tax_benefit_model_id == tax_benefit_model_id)
    policies = session.exec(query).all()
    return [_policy_to_read(p) for p in policies]


@router.get("/{policy_id}", response_model=PolicyRead)
def get_policy(policy_id: UUID, session: Session = Depends(get_session)):
    """Get a specific policy."""
    query = (
        select(Policy)
        .where(Policy.id == policy_id)
        .options(
            selectinload(Policy.parameter_values).selectinload(ParameterValue.parameter)
        )
    )
    policy = session.exec(query).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return _policy_to_read(policy)
