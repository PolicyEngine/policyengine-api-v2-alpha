"""Staging integration tests — HTTP-based, run against deployed API.

Usage:
    API_BASE_URL=https://staging---service.a.run.app pytest tests/test_staging_api.py -v
"""

import os

import httpx
import pytest

pytestmark = pytest.mark.staging

BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="module")
def api():
    """HTTP client for the staging API."""
    with httpx.Client(base_url=BASE_URL, timeout=30.0, follow_redirects=True) as client:
        yield client


def test_health(api):
    r = api.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_list_models(api):
    r = api.get("/tax-benefit-models")
    assert r.status_code == 200
    models = r.json()
    assert len(models) >= 2  # UK and US


def test_list_variables(api):
    r = api.get("/variables", params={"country_id": "us", "limit": 5})
    assert r.status_code == 200


def test_list_parameters(api):
    r = api.get("/parameters", params={"country_id": "us", "limit": 5})
    assert r.status_code == 200
