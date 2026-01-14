"""API routers."""

from fastapi import APIRouter

from . import (
    agent,
    analysis,
    change_aggregates,
    datasets,
    dynamics,
    household,
    outputs,
    parameter_values,
    parameters,
    policies,
    simulations,
    tax_benefit_model_versions,
    tax_benefit_models,
    user_policies,
    variables,
)

api_router = APIRouter()

api_router.include_router(datasets.router)
api_router.include_router(policies.router)
api_router.include_router(simulations.router)
api_router.include_router(outputs.router)
api_router.include_router(variables.router)
api_router.include_router(parameters.router)
api_router.include_router(parameter_values.router)
api_router.include_router(dynamics.router)
api_router.include_router(tax_benefit_models.router)
api_router.include_router(tax_benefit_model_versions.router)
api_router.include_router(change_aggregates.router)
api_router.include_router(household.router)
api_router.include_router(analysis.router)
api_router.include_router(agent.router)
api_router.include_router(user_policies.router)

__all__ = ["api_router"]
