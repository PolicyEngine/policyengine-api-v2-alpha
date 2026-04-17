"""Regression tests for batch size caps on aggregate endpoints (#269)."""

import uuid

from fastapi.testclient import TestClient

from policyengine_api.api import change_aggregates as change_aggregates_api
from policyengine_api.api import outputs as outputs_api
from policyengine_api.main import app

client = TestClient(app)


def _build_aggregate_payload(n: int) -> list[dict]:
    sim_id = str(uuid.uuid4())
    return [
        {
            "simulation_id": sim_id,
            "variable_name": "x",
            "aggregation_function": "sum",
        }
        for _ in range(n)
    ]


def _build_change_aggregate_payload(n: int) -> list[dict]:
    baseline_id = str(uuid.uuid4())
    reform_id = str(uuid.uuid4())
    return [
        {
            "baseline_simulation_id": baseline_id,
            "reform_simulation_id": reform_id,
            "variable_name": "x",
            "aggregation_function": "sum",
        }
        for _ in range(n)
    ]


def test_create_aggregate_outputs_rejects_oversize_batch():
    assert outputs_api.MAX_BATCH_SIZE == 100
    resp = client.post(
        "/outputs/aggregates",
        json=_build_aggregate_payload(outputs_api.MAX_BATCH_SIZE + 1),
    )
    assert resp.status_code == 422
    assert "at most 100" in resp.text


def test_create_change_aggregates_rejects_oversize_batch():
    assert change_aggregates_api.MAX_BATCH_SIZE == 100
    resp = client.post(
        "/outputs/change-aggregates",
        json=_build_change_aggregate_payload(change_aggregates_api.MAX_BATCH_SIZE + 1),
    )
    assert resp.status_code == 422
    assert "at most 100" in resp.text
