"""Security regression tests for remote attack surface hardening."""

from fastapi import HTTPException, Request

from policyengine_api.config.settings import settings
from policyengine_api.main import app
from policyengine_api.security import require_expensive_endpoint_access
from scripts.init import build_rls_policies_sql


def _make_request(
    path: str, client_host: str = "203.0.113.10", headers: dict | None = None
) -> Request:
    raw_headers = [(b"host", b"api.policyengine.org")]
    for key, value in (headers or {}).items():
        raw_headers.append((key.lower().encode("ascii"), value.encode("ascii")))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": raw_headers,
        "client": (client_host, 443),
        "server": ("api.policyengine.org", 443),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


def test_expensive_endpoint_guard_blocks_external_requests_without_key():
    request = _make_request("/analysis/economic-impact")

    try:
        require_expensive_endpoint_access(request)
    except HTTPException as exc:
        assert exc.status_code == 401
    else:
        raise AssertionError("expected external requests without a key to be rejected")


def test_expensive_endpoint_guard_blocks_testclient_without_key():
    request = _make_request("/analysis/economic-impact", client_host="testclient")

    try:
        require_expensive_endpoint_access(request)
    except HTTPException as exc:
        assert exc.status_code == 401
    else:
        raise AssertionError(
            "expected testclient requests without a key to be rejected"
        )


def test_expensive_endpoint_guard_allows_external_requests_with_key(monkeypatch):
    monkeypatch.setattr(settings, "expensive_endpoint_api_key", "secret-key")
    request = _make_request(
        "/analysis/economic-impact",
        headers={"X-PolicyEngine-Api-Key": "secret-key"},
    )

    assert (
        require_expensive_endpoint_access(request, x_policyengine_api_key="secret-key")
        is None
    )


def test_expensive_routes_are_protected():
    protected_routes = {
        ("POST", "/analysis/economic-impact"),
        ("GET", "/analysis/economic-impact/{report_id}"),
        ("POST", "/analysis/economy-custom"),
        ("GET", "/analysis/economy-custom/{report_id}"),
        ("POST", "/analysis/rerun/{report_id}"),
        ("POST", "/policies/"),
        ("POST", "/dynamics/"),
        ("POST", "/household/calculate"),
        ("POST", "/household/impact"),
        ("POST", "/analysis/household-impact"),
        ("GET", "/analysis/household-impact/{report_id}"),
        ("POST", "/outputs/aggregates"),
        ("GET", "/outputs/aggregates"),
        ("GET", "/outputs/aggregates/{output_id}"),
        ("POST", "/outputs/change-aggregates"),
        ("GET", "/outputs/change-aggregates"),
        ("GET", "/outputs/change-aggregates/{output_id}"),
        ("POST", "/agent/run"),
        ("POST", "/agent/log/{call_id}"),
        ("POST", "/agent/complete/{call_id}"),
    }

    route_map = {}
    for route in app.routes:
        methods = getattr(route, "methods", None)
        if not methods:
            continue
        for method in methods:
            if method in {"GET", "POST"}:
                route_map[(method, route.path)] = route

    for route_key in protected_routes:
        route = route_map[route_key]
        assert any(
            getattr(dependency.call, "__name__", "")
            == "require_expensive_endpoint_access"
            for dependency in route.dependant.dependencies
        ), route_key


def test_cors_allows_configured_local_origin(client):
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_rejects_unconfigured_origin(client):
    response = client.get(
        "/health",
        headers={"Origin": "https://evil.example"},
    )

    assert response.headers.get("access-control-allow-origin") is None


def test_init_rls_sql_does_not_grant_anonymous_database_access():
    sql = build_rls_policies_sql()
    service_role_only_tables = {
        "simulations",
        "policies",
        "dynamics",
        "reports",
        "household_jobs",
        "households",
        "aggregates",
        "change_aggregates",
        "decile_impacts",
        "program_statistics",
        "user_household_associations",
        "poverty",
        "inequality",
    }

    assert "TO anon" not in sql
    assert 'CREATE POLICY "Public read access" ON datasets' in sql
    assert "FOR SELECT TO authenticated" in sql
    for table in service_role_only_tables:
        assert f'CREATE POLICY "Users can create" ON {table}' not in sql
        assert f'CREATE POLICY "Users can read" ON {table}' not in sql
        assert f'CREATE POLICY "Public read access" ON {table}' not in sql
    assert (
        'DROP POLICY IF EXISTS "Users can manage own associations" '
        "ON user_household_associations;"
    ) in sql
