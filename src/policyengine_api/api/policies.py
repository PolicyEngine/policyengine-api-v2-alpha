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

from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from policyengine_api.models import (
    Parameter,
    ParameterValue,
    Policy,
    PolicyCreate,
    PolicyRead,
)
from policyengine_api.services.database import get_session

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
    # Create the policy
    db_policy = Policy(name=policy.name, description=policy.description)
    session.add(db_policy)
    session.flush()  # Get the policy ID before adding parameter values

    # Create associated parameter values
    for pv_data in policy.parameter_values:
        # Validate parameter exists
        param = session.get(Parameter, pv_data["parameter_id"])
        if not param:
            raise HTTPException(
                status_code=404,
                detail=f"Parameter {pv_data['parameter_id']} not found",
            )

        # Parse dates
        start_date = (
            datetime.fromisoformat(pv_data["start_date"].replace("Z", "+00:00"))
            if isinstance(pv_data["start_date"], str)
            else pv_data["start_date"]
        )
        end_date = None
        if pv_data.get("end_date"):
            end_date = (
                datetime.fromisoformat(pv_data["end_date"].replace("Z", "+00:00"))
                if isinstance(pv_data["end_date"], str)
                else pv_data["end_date"]
            )

        # Create parameter value
        db_pv = ParameterValue(
            parameter_id=pv_data["parameter_id"],
            value_json=pv_data["value_json"],
            start_date=start_date,
            end_date=end_date,
            policy_id=db_policy.id,
        )
        session.add(db_pv)

    session.commit()
    session.refresh(db_policy)
    return db_policy


@router.get("/", response_model=List[PolicyRead])
def list_policies(session: Session = Depends(get_session)):
    """List all policies."""
    policies = session.exec(select(Policy)).all()
    return policies


@router.get("/{policy_id}", response_model=PolicyRead)
def get_policy(policy_id: UUID, session: Session = Depends(get_session)):
    """Get a specific policy."""
    policy = session.get(Policy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy
