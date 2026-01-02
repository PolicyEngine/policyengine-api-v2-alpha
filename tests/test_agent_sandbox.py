"""Tests for the agent sandbox using Claude Agent SDK with MCP."""

import pytest

from policyengine_api.agent_sandbox import _run_agent_impl


@pytest.mark.integration
def test_basic_arithmetic():
    """Agent can do simple math."""
    result = _run_agent_impl("What is 2 + 2?", max_turns=3)
    assert result["status"] == "completed"
    assert "4" in result["result"]


@pytest.mark.integration
def test_uk_personal_allowance():
    """Agent can find UK personal allowance value."""
    result = _run_agent_impl(
        "What is the UK personal allowance for 2026?",
        max_turns=15,
    )
    assert result["status"] == "completed"
    assert "12,570" in result["result"] or "12570" in result["result"]


@pytest.mark.integration
def test_uk_household_calculation():
    """Agent calculates UK income tax correctly."""
    result = _run_agent_impl(
        "Calculate income tax for someone earning £50,000 in the UK in 2026. "
        "Poll until the calculation completes and give me the result.",
        max_turns=20,
    )
    assert result["status"] == "completed"
    assert "tax" in result["result"].lower()


@pytest.mark.integration
@pytest.mark.slow
def test_economic_impact_personal_allowance():
    """Agent can run economic impact for personal allowance change."""
    result = _run_agent_impl(
        "What would be the budgetary impact of setting the UK personal allowance to £10,000? "
        "Create the policy, run the analysis, and poll until complete.",
        max_turns=25,
    )
    assert result["status"] == "completed"
    assert any(
        word in result["result"].lower()
        for word in ["budget", "cost", "revenue", "billion", "impact", "decile"]
    )
