"""Tests for the agent sandbox using direct Claude API with OpenAPI-generated tools."""

import pytest

from policyengine_api.agent_sandbox import (
    _run_agent_impl,
    fetch_openapi_spec,
    openapi_to_claude_tools,
)


def test_openapi_tool_generation():
    """OpenAPI spec generates tools correctly."""
    spec = fetch_openapi_spec("https://v2.api.policyengine.org")
    tools = openapi_to_claude_tools(spec)

    assert len(tools) > 30  # Should have many endpoints
    tool_names = [t["name"] for t in tools]

    # Check key endpoints exist
    assert any("parameters" in n for n in tool_names)
    assert any("household" in n for n in tool_names)
    assert any("policies" in n for n in tool_names)


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
    # Should mention income tax amount
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
    # Should mention some impact metric
    assert any(
        word in result["result"].lower()
        for word in ["budget", "cost", "revenue", "billion", "impact", "decile"]
    )
