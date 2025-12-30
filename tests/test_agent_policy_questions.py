"""Integration tests for agent policy questions.

These tests run real agent queries and measure turn counts.
Run with: pytest tests/test_agent_policy_questions.py -v -s

The goal is to track agent performance and identify opportunities
to improve API metadata/documentation to reduce turns needed.
"""

import pytest

pytestmark = pytest.mark.integration

from policyengine_api.agent_sandbox import _run_agent_impl

# Use production API for now - tests are read-only
API_BASE = "https://v2.api.policyengine.org"


class TestUKHouseholdSimple:
    """Simple UK household questions - should complete in 2-4 turns."""

    def test_income_tax_calculation(self):
        """Basic income tax calculation."""
        result = _run_agent_impl(
            "What is my income tax if I earn £50,000 per year in the UK?",
            api_base_url=API_BASE,
            max_turns=10,
        )
        assert result["status"] == "completed"
        assert result["result"] is not None
        # Should mention tax amount
        assert "£" in result["result"] or "GBP" in result["result"]
        print(f"\nTurns: {result['turns']}")
        print(f"Result: {result['result'][:500]}")

    def test_child_benefit_lookup(self):
        """Child benefit for a family."""
        result = _run_agent_impl(
            "How much child benefit would a UK family with 2 children receive per week?",
            api_base_url=API_BASE,
            max_turns=10,
        )
        assert result["status"] == "completed"
        assert result["result"] is not None
        print(f"\nTurns: {result['turns']}")
        print(f"Result: {result['result'][:500]}")

    def test_personal_allowance(self):
        """Simple parameter lookup."""
        result = _run_agent_impl(
            "What is the current UK personal allowance?",
            api_base_url=API_BASE,
            max_turns=10,
        )
        assert result["status"] == "completed"
        assert result["result"] is not None
        # Should mention the amount (currently £12,570)
        assert "12" in result["result"]
        print(f"\nTurns: {result['turns']}")
        print(f"Result: {result['result'][:500]}")


class TestUKHouseholdComplex:
    """Complex UK household questions - may need 4-8 turns."""

    def test_marginal_rate_at_100k(self):
        """Marginal tax rate calculation at £100k (60% trap)."""
        result = _run_agent_impl(
            "What is the effective marginal tax rate for someone earning £100,000 in the UK? "
            "Include the personal allowance taper.",
            api_base_url=API_BASE,
            max_turns=15,
        )
        assert result["status"] == "completed"
        assert result["result"] is not None
        # Should mention high marginal rate (60% or similar)
        print(f"\nTurns: {result['turns']}")
        print(f"Result: {result['result'][:500]}")

    def test_reform_comparison(self):
        """Compare baseline vs reform for a household."""
        result = _run_agent_impl(
            "Compare the net income for someone earning £40,000 under current UK tax law "
            "versus if the basic rate of income tax was 25% instead of 20%.",
            api_base_url=API_BASE,
            max_turns=15,
        )
        assert result["status"] == "completed"
        assert result["result"] is not None
        print(f"\nTurns: {result['turns']}")
        print(f"Result: {result['result'][:500]}")


class TestUSHouseholdSimple:
    """Simple US household questions - should complete in 2-4 turns."""

    def test_federal_income_tax(self):
        """Basic federal income tax calculation."""
        result = _run_agent_impl(
            "What is my federal income tax if I earn $75,000 per year in the US?",
            api_base_url=API_BASE,
            max_turns=10,
        )
        assert result["status"] == "completed"
        assert result["result"] is not None
        assert "$" in result["result"] or "USD" in result["result"]
        print(f"\nTurns: {result['turns']}")
        print(f"Result: {result['result'][:500]}")

    def test_snap_eligibility(self):
        """SNAP benefit calculation."""
        result = _run_agent_impl(
            "How much SNAP (food stamps) would a family of 4 with $30,000 annual income "
            "receive in the US?",
            api_base_url=API_BASE,
            max_turns=10,
        )
        assert result["status"] == "completed"
        assert result["result"] is not None
        print(f"\nTurns: {result['turns']}")
        print(f"Result: {result['result'][:500]}")

    def test_standard_deduction(self):
        """Simple parameter lookup."""
        result = _run_agent_impl(
            "What is the US federal standard deduction for a single filer in 2024?",
            api_base_url=API_BASE,
            max_turns=10,
        )
        assert result["status"] == "completed"
        assert result["result"] is not None
        print(f"\nTurns: {result['turns']}")
        print(f"Result: {result['result'][:500]}")


class TestUSHouseholdComplex:
    """Complex US household questions - may need 4-8 turns."""

    def test_eitc_calculation(self):
        """EITC with children calculation."""
        result = _run_agent_impl(
            "Calculate the Earned Income Tax Credit for a single parent with 2 children "
            "earning $25,000 per year in the US.",
            api_base_url=API_BASE,
            max_turns=15,
        )
        assert result["status"] == "completed"
        assert result["result"] is not None
        print(f"\nTurns: {result['turns']}")
        print(f"Result: {result['result'][:500]}")


class TestEconomySimple:
    """Simple economy-wide questions - parameter lookups."""

    def test_uk_higher_rate_threshold(self):
        """UK higher rate threshold lookup."""
        result = _run_agent_impl(
            "At what income level does the UK higher rate (40%) tax band start?",
            api_base_url=API_BASE,
            max_turns=10,
        )
        assert result["status"] == "completed"
        assert result["result"] is not None
        # Should mention £50,270 or similar
        assert "50" in result["result"]
        print(f"\nTurns: {result['turns']}")
        print(f"Result: {result['result'][:500]}")


class TestTurnCounting:
    """Tests specifically to measure turn efficiency."""

    @pytest.mark.parametrize(
        "question,max_expected_turns",
        [
            ("What is the UK personal allowance?", 4),
            ("What is the US standard deduction?", 4),
            ("Calculate income tax for £30,000 UK salary", 5),
            ("Calculate federal income tax for $50,000 US salary", 5),
        ],
    )
    def test_turn_efficiency(self, question, max_expected_turns):
        """Verify agent completes within expected turn count."""
        result = _run_agent_impl(
            question,
            api_base_url=API_BASE,
            max_turns=max_expected_turns + 5,  # Allow some buffer
        )
        assert result["status"] == "completed"
        print(f"\nQuestion: {question}")
        print(f"Turns: {result['turns']} (max expected: {max_expected_turns})")
        print(f"Result: {result['result'][:300]}")

        # Soft assertion - log warning if over expected
        if result["turns"] > max_expected_turns:
            print(f"WARNING: Took {result['turns']} turns, expected <= {max_expected_turns}")
