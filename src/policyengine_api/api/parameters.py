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

from policyengine_api.config.constants import COUNTRY_MODEL_NAMES, CountryId
from policyengine_api.models import (
    Parameter,
    ParameterNode,
    ParameterRead,
    TaxBenefitModel,
    TaxBenefitModelVersion,
)
from policyengine_api.services.database import get_session

router = APIRouter(prefix="/parameters", tags=["parameters"])


@router.get("/", response_model=List[ParameterRead])
def list_parameters(
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
    tax_benefit_model_name: str | None = None,
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
    """
    query = select(Parameter)

    # Filter by tax benefit model name (country)
    if tax_benefit_model_name:
        query = (
            query.join(TaxBenefitModelVersion)
            .join(TaxBenefitModel)
            .where(TaxBenefitModel.name == tax_benefit_model_name)
        )

    if search:
        # Case-insensitive search using ILIKE
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

    model_name = COUNTRY_MODEL_NAMES[request.country_id]

    query = (
        select(Parameter)
        .join(TaxBenefitModelVersion)
        .join(TaxBenefitModel)
        .where(TaxBenefitModel.name == model_name)
        .where(Parameter.name.in_(request.names))
        .order_by(Parameter.name)
    )

    return session.exec(query).all()


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
    session: Session = Depends(get_session),
) -> ParameterChildrenResponse:
    """Get direct children of a parameter path for tree navigation.

    Returns both intermediate nodes (folders with child_count) and leaf
    parameters (with full metadata). Use this to lazily load the parameter
    tree one level at a time.
    """
    model_name = COUNTRY_MODEL_NAMES[country_id]
    prefix = f"{parent_path}." if parent_path else ""

    # Fetch all parameters under this path
    param_query = (
        select(Parameter)
        .join(TaxBenefitModelVersion)
        .join(TaxBenefitModel)
        .where(TaxBenefitModel.name == model_name)
        .where(Parameter.name.startswith(prefix))
    )
    descendants = session.exec(param_query).all()

    # Fetch all parameter nodes under this path for labels
    node_query = (
        select(ParameterNode)
        .join(TaxBenefitModelVersion)
        .join(TaxBenefitModel)
        .where(TaxBenefitModel.name == model_name)
        .where(ParameterNode.name.startswith(prefix))
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
