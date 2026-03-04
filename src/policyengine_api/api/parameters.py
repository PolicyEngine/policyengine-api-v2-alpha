"""Parameter metadata endpoints.

Parameters are the policy levers that can be modified in reforms (e.g. tax rates,
benefit amounts, thresholds). Use these endpoints to discover available parameters.
Parameter names are used when creating policy reforms.
"""

from __future__ import annotations

from typing import List, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from policyengine_api.models import (
    Parameter,
    ParameterRead,
)
from policyengine_api.services.database import get_session
from policyengine_api.services.tax_benefit_models import resolve_model_version_id

router = APIRouter(prefix="/parameters", tags=["parameters"])


@router.get("/", response_model=List[ParameterRead])
def list_parameters(
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
    tax_benefit_model_name: str | None = None,
    tax_benefit_model_version_id: UUID | None = None,
    session: Session = Depends(get_session),
):
    """List available parameters with pagination and search.

    Parameters are policy levers (e.g. tax rates, thresholds, benefit amounts)
    that can be modified in reforms. Use parameter names when creating policies.

    Args:
        search: Filter by parameter name, label, or description.
        tax_benefit_model_name: Filter by country model.
            Use "policyengine-uk" for UK parameters.
            Use "policyengine-us" for US parameters.
            Defaults to the latest model version when no version ID is given.
        tax_benefit_model_version_id: Filter by a specific model version.
            Takes precedence over tax_benefit_model_name.
    """
    query = select(Parameter)

    version_id = resolve_model_version_id(
        tax_benefit_model_name, tax_benefit_model_version_id, session
    )
    if version_id:
        query = query.where(Parameter.tax_benefit_model_version_id == version_id)

    if search:
        search_pattern = f"%{search}%"
        search_filter = (
            Parameter.name.ilike(search_pattern)
            | Parameter.label.ilike(search_pattern)
            | Parameter.description.ilike(search_pattern)
        )
        query = query.where(search_filter)

    parameters = session.exec(
        query.order_by(Parameter.name).offset(skip).limit(limit)
    ).all()
    return parameters


class ParameterByNameRequest(BaseModel):
    """Request body for looking up parameters by name."""

    names: list[str]
    tax_benefit_model_name: str
    tax_benefit_model_version_id: UUID | None = None


@router.post("/by-name", response_model=List[ParameterRead])
def get_parameters_by_name(
    request: ParameterByNameRequest,
    session: Session = Depends(get_session),
):
    """Look up parameters by their exact names.

    Given a list of parameter paths (e.g. "gov.hmrc.income_tax.rates.uk[0].rate"),
    returns the full metadata for each matching parameter. Names that don't match
    any parameter are silently omitted from the response.

    Use this to fetch metadata for a known set of parameters (e.g. all parameters
    referenced in a user's saved policy) without loading the entire parameter catalog.
    """
    if not request.names:
        return []

    version_id = resolve_model_version_id(
        request.tax_benefit_model_name,
        request.tax_benefit_model_version_id,
        session,
    )

    query = select(Parameter).where(Parameter.name.in_(request.names))
    if version_id:
        query = query.where(Parameter.tax_benefit_model_version_id == version_id)

    return session.exec(query.order_by(Parameter.name)).all()


class ParameterChild(BaseModel):
    """A single child in the parameter tree."""

    path: str
    label: str
    type: Literal["node", "parameter"]
    child_count: int | None = None
    parameter: ParameterRead | None = None


class ParameterChildrenResponse(BaseModel):
    """Response for the parameter children endpoint."""

    parent_path: str
    children: list[ParameterChild]


@router.get("/children", response_model=ParameterChildrenResponse)
def get_parameter_children(
    tax_benefit_model_name: str = Query(
        description='Model name (e.g. "policyengine-us" or "policyengine-uk")'
    ),
    parent_path: str = Query(
        default="", description="Parent parameter path (e.g. 'gov' or 'gov.hmrc')"
    ),
    tax_benefit_model_version_id: UUID | None = Query(
        default=None, description="Optional specific model version ID"
    ),
    session: Session = Depends(get_session),
) -> ParameterChildrenResponse:
    """Get direct children of a parameter path for tree navigation.

    Returns both intermediate nodes (folders with child_count) and leaf
    parameters (with full metadata). Use this to lazily load the parameter
    tree one level at a time.
    """
    version_id = resolve_model_version_id(
        tax_benefit_model_name, tax_benefit_model_version_id, session
    )

    prefix = f"{parent_path}." if parent_path else ""

    query = select(Parameter).where(Parameter.name.startswith(prefix))
    if version_id:
        query = query.where(Parameter.tax_benefit_model_version_id == version_id)

    descendants = session.exec(query).all()

    # Group by direct child path
    children_map: dict[str, dict] = {}
    prefix_len = len(prefix)

    for param in descendants:
        remainder = param.name[prefix_len:]
        dot_pos = remainder.find(".")

        if dot_pos == -1:
            # Direct child (leaf at this level)
            child_path = param.name
            if child_path not in children_map:
                children_map[child_path] = {
                    "direct_param": None,
                    "descendant_count": 0,
                }
            children_map[child_path]["direct_param"] = param
        else:
            # Deeper descendant — extract direct child segment
            segment = remainder[:dot_pos]
            child_path = prefix + segment
            if child_path not in children_map:
                children_map[child_path] = {
                    "direct_param": None,
                    "descendant_count": 0,
                }
            children_map[child_path]["descendant_count"] += 1

    # Build response
    children = []
    for path in sorted(children_map):
        info = children_map[path]
        if info["descendant_count"] > 0:
            # Node: has children below it
            direct_param = info["direct_param"]
            label = (
                direct_param.label
                if direct_param and direct_param.label
                else path.rsplit(".", 1)[-1]
            )
            children.append(
                ParameterChild(
                    path=path,
                    label=label,
                    type="node",
                    child_count=info["descendant_count"],
                )
            )
        elif info["direct_param"]:
            # Leaf parameter
            param = info["direct_param"]
            children.append(
                ParameterChild(
                    path=path,
                    label=param.label or path.rsplit(".", 1)[-1],
                    type="parameter",
                    parameter=ParameterRead.model_validate(param),
                )
            )

    return ParameterChildrenResponse(parent_path=parent_path, children=children)


@router.get("/{parameter_id}", response_model=ParameterRead)
def get_parameter(parameter_id: UUID, session: Session = Depends(get_session)):
    """Get a specific parameter."""
    parameter = session.get(Parameter, parameter_id)
    if not parameter:
        raise HTTPException(status_code=404, detail="Parameter not found")
    return parameter
