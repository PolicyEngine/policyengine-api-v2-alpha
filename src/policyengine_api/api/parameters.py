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

from policyengine_api.config.constants import CountryId
from policyengine_api.models import (
    Parameter,
    ParameterNode,
    ParameterRead,
)
from policyengine_api.services.database import get_session
from policyengine_api.services.model_resolver import resolve_version_id

router = APIRouter(prefix="/parameters", tags=["parameters"])


@router.get("/", response_model=List[ParameterRead])
def list_parameters(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    search: str | None = None,
    country_id: CountryId | None = None,
    tax_benefit_model_version_id: UUID | None = None,
    session: Session = Depends(get_session),
):
    """List available parameters with pagination and search.

    Parameters are policy levers (e.g. tax rates, thresholds, benefit amounts)
    that can be modified in reforms. Use parameter names when creating policies.

    Args:
        search: Filter by parameter name, label, or description.
        country_id: Filter by country ("us" or "uk").
            Defaults to the latest model version.
        tax_benefit_model_version_id: Pin to a specific model version.
            Takes precedence over country_id.
    """
    query = select(Parameter)

    version_id = resolve_version_id(country_id, tax_benefit_model_version_id, session)
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
    country_id: CountryId
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

    version_id = resolve_version_id(
        request.country_id, request.tax_benefit_model_version_id, session
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
    country_id: CountryId = Query(description='Country ID ("us" or "uk")'),
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
    version_id = resolve_version_id(country_id, tax_benefit_model_version_id, session)

    prefix = f"{parent_path}." if parent_path else ""

    # Fetch all parameters under this path
    param_query = select(Parameter).where(Parameter.name.startswith(prefix))
    if version_id:
        param_query = param_query.where(
            Parameter.tax_benefit_model_version_id == version_id
        )
    descendants = session.exec(param_query).all()

    # Fetch all parameter nodes under this path for labels
    node_query = select(ParameterNode).where(ParameterNode.name.startswith(prefix))
    if version_id:
        node_query = node_query.where(
            ParameterNode.tax_benefit_model_version_id == version_id
        )
    nodes = session.exec(node_query).all()

    # Build a map of node path -> label for quick lookup
    node_labels: dict[str, str | None] = {node.name: node.label for node in nodes}

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
            # Priority: 1) parameter_nodes label, 2) direct_param label, 3) path segment
            direct_param = info["direct_param"]
            label = node_labels.get(path)
            if not label and direct_param and direct_param.label:
                label = direct_param.label
            if not label:
                label = path.rsplit(".", 1)[-1]
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
