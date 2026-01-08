"""Tests for agent results upload endpoints."""

import pytest
from fastapi.testclient import TestClient


def test_create_policy_with_modifier(client: TestClient):
    """Test creating a policy with simulation_modifier."""
    modifier_code = '''
def modify(simulation):
    from numpy import where
    print("Modifier applied")
'''

    response = client.post(
        "/agent/results/policy-with-modifier",
        json={
            "name": "Test structural reform",
            "description": "A test policy with custom variable logic",
            "simulation_modifier": modifier_code,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["policy_id"] is not None
    assert data["has_modifier"] is True
    assert data["name"] == "Test structural reform"

    # Verify we can fetch the policy and it has the modifier
    policy_id = data["policy_id"]
    get_response = client.get(f"/policies/{policy_id}")
    assert get_response.status_code == 200
    policy_data = get_response.json()
    assert policy_data["simulation_modifier"] == modifier_code


def test_create_policy_without_modifier(client: TestClient):
    """Test creating a policy without simulation_modifier."""
    response = client.post(
        "/agent/results/policy-with-modifier",
        json={
            "name": "Test param-only policy",
            "description": "A policy without custom variable logic",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["has_modifier"] is False


def test_execute_python_basic():
    """Test the execute_python_code function directly."""
    from policyengine_api.agent_sandbox import execute_python_code

    # Test basic execution
    result = execute_python_code('print("Hello from test")')
    assert "Hello from test" in result

    # Test with numpy (common in modifiers)
    result = execute_python_code("""
from numpy import where, array
arr = array([10000, 25000, 50000])
benefits = where(arr < 20000, 1000, 0)
print(f"Benefits: {benefits}")
""")
    assert "Benefits:" in result
    assert "1000" in result


def test_execute_python_catches_errors():
    """Test that execute_python catches and reports errors."""
    from policyengine_api.agent_sandbox import execute_python_code

    # Test syntax error
    result = execute_python_code("def broken(")
    assert "Error:" in result or "SyntaxError" in result

    # Test runtime error
    result = execute_python_code("x = 1/0")
    assert "ZeroDivisionError" in result


def test_execute_python_modifier_validation():
    """Test validating a simulation modifier with execute_python."""
    from policyengine_api.agent_sandbox import execute_python_code

    # Test a realistic modifier pattern
    modifier_code = """
from numpy import where

def modify(simulation):
    # This would normally modify the simulation
    # For testing, just verify the function is defined correctly
    pass

# Validation
print(f"modify is callable: {callable(modify)}")
print(f"modify takes 1 arg: {modify.__code__.co_argcount == 1}")

# Test the logic we'd use in a formula
income = 15000
threshold = 20000
amount = 1000
benefit = amount if income < threshold else 0
print(f"Test case: income={income}, benefit={benefit}")
assert benefit == 1000, "Logic check failed"
print("All checks passed!")
"""

    result = execute_python_code(modifier_code)
    assert "modify is callable: True" in result
    assert "All checks passed!" in result


def test_policy_read_includes_modifier(client: TestClient):
    """Test that PolicyRead schema includes simulation_modifier."""
    # Create a policy with modifier
    modifier = "def modify(sim): pass"
    response = client.post(
        "/agent/results/policy-with-modifier",
        json={
            "name": "Modifier visibility test",
            "simulation_modifier": modifier,
        },
    )
    assert response.status_code == 200
    policy_id = response.json()["policy_id"]

    # Fetch via standard policies endpoint
    response = client.get(f"/policies/{policy_id}")
    assert response.status_code == 200
    data = response.json()

    # The simulation_modifier should be visible in the response
    assert "simulation_modifier" in data
    assert data["simulation_modifier"] == modifier
