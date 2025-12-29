"""Tests for the agent sandbox using direct Claude API."""

import pytest

from policyengine_api.agent_sandbox import _run_agent_impl


@pytest.mark.integration
def test_basic_arithmetic():
    """Agent can do simple math."""
    result = _run_agent_impl("What is 2 + 2?")
    assert result["status"] == "completed"
    assert "4" in result["result"]


@pytest.mark.integration
def test_uk_household_calculation():
    """Agent calculates UK income tax correctly."""
    result = _run_agent_impl(
        "Calculate income tax for someone earning £35,000 in the UK in 2026"
    )
    assert result["status"] == "completed"
    assert "tax" in result["result"].lower()


@pytest.mark.integration
def test_parameter_search():
    """Agent can search for policy parameters."""
    result = _run_agent_impl("Search for UK personal allowance parameters")
    assert result["status"] == "completed"
    assert (
        "personal" in result["result"].lower()
        or "allowance" in result["result"].lower()
    )


@pytest.mark.integration
def test_get_personal_allowance_value():
    """Agent can retrieve the current personal allowance value."""
    result = _run_agent_impl("What is the current UK personal allowance amount?")
    assert result["status"] == "completed"
    # Should return a reasonable value (around £12,570)
    assert any(str(x) in result["result"] for x in ["12570", "12,570"])


@pytest.mark.integration
@pytest.mark.slow
def test_economic_impact_personal_allowance():
    """Agent can run economic impact for personal allowance change to £10k."""
    result = _run_agent_impl(
        "What would be the budgetary impact of setting the UK personal allowance to £10,000?",
        max_turns=15,
    )
    assert result["status"] == "completed"
    # Should mention budget/cost/revenue in response
    assert any(
        word in result["result"].lower()
        for word in ["budget", "cost", "revenue", "billion", "bn", "impact"]
    )
