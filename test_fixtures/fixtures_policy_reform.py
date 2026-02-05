"""Fixtures for policy reform conversion tests."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


# =============================================================================
# Mock objects for testing _pe_policy_to_reform_dict
# =============================================================================


@dataclass
class MockParameter:
    """Mock policyengine.core.models.parameter.Parameter."""

    name: str


@dataclass
class MockParameterValue:
    """Mock policyengine.core.models.parameter_value.ParameterValue."""

    parameter: MockParameter | None
    value: Any
    start_date: date | datetime | str | None


@dataclass
class MockPolicy:
    """Mock policyengine.core.policy.Policy."""

    parameter_values: list[MockParameterValue] | None


# =============================================================================
# Test data constants
# =============================================================================

# Simple policy with single parameter change
SIMPLE_POLICY = MockPolicy(
    parameter_values=[
        MockParameterValue(
            parameter=MockParameter(name="gov.irs.credits.ctc.amount.base"),
            value=3000,
            start_date=date(2024, 1, 1),
        )
    ]
)

SIMPLE_POLICY_EXPECTED = {
    "gov.irs.credits.ctc.amount.base": {"2024-01-01": 3000}
}

# Policy with multiple parameter changes
MULTI_PARAM_POLICY = MockPolicy(
    parameter_values=[
        MockParameterValue(
            parameter=MockParameter(name="gov.irs.credits.ctc.amount.base"),
            value=3000,
            start_date=date(2024, 1, 1),
        ),
        MockParameterValue(
            parameter=MockParameter(name="gov.irs.credits.ctc.refundable.fully_refundable"),
            value=True,
            start_date=date(2024, 1, 1),
        ),
        MockParameterValue(
            parameter=MockParameter(name="gov.irs.income.bracket.rates.1"),
            value=0.12,
            start_date=date(2024, 1, 1),
        ),
    ]
)

MULTI_PARAM_POLICY_EXPECTED = {
    "gov.irs.credits.ctc.amount.base": {"2024-01-01": 3000},
    "gov.irs.credits.ctc.refundable.fully_refundable": {"2024-01-01": True},
    "gov.irs.income.bracket.rates.1": {"2024-01-01": 0.12},
}

# Policy with same parameter at different dates
MULTI_DATE_POLICY = MockPolicy(
    parameter_values=[
        MockParameterValue(
            parameter=MockParameter(name="gov.irs.credits.ctc.amount.base"),
            value=2500,
            start_date=date(2024, 1, 1),
        ),
        MockParameterValue(
            parameter=MockParameter(name="gov.irs.credits.ctc.amount.base"),
            value=3000,
            start_date=date(2025, 1, 1),
        ),
    ]
)

MULTI_DATE_POLICY_EXPECTED = {
    "gov.irs.credits.ctc.amount.base": {
        "2024-01-01": 2500,
        "2025-01-01": 3000,
    }
}

# Policy with datetime start_date (has time component)
DATETIME_POLICY = MockPolicy(
    parameter_values=[
        MockParameterValue(
            parameter=MockParameter(name="gov.irs.credits.ctc.amount.base"),
            value=3000,
            start_date=datetime(2024, 1, 1, 12, 30, 45),
        )
    ]
)

DATETIME_POLICY_EXPECTED = {
    "gov.irs.credits.ctc.amount.base": {"2024-01-01": 3000}
}

# Policy with ISO string start_date
ISO_STRING_POLICY = MockPolicy(
    parameter_values=[
        MockParameterValue(
            parameter=MockParameter(name="gov.irs.credits.ctc.amount.base"),
            value=3000,
            start_date="2024-01-01T00:00:00",
        )
    ]
)

ISO_STRING_POLICY_EXPECTED = {
    "gov.irs.credits.ctc.amount.base": {"2024-01-01": 3000}
}

# Empty policy (no parameter values)
EMPTY_POLICY = MockPolicy(parameter_values=[])

# None policy
NONE_POLICY = None

# Policy with None parameter_values
NONE_PARAM_VALUES_POLICY = MockPolicy(parameter_values=None)

# Policy with invalid entries (missing parameter or start_date)
INVALID_ENTRIES_POLICY = MockPolicy(
    parameter_values=[
        MockParameterValue(
            parameter=None,  # Missing parameter
            value=3000,
            start_date=date(2024, 1, 1),
        ),
        MockParameterValue(
            parameter=MockParameter(name="gov.irs.credits.ctc.amount.base"),
            value=3000,
            start_date=None,  # Missing start_date
        ),
        MockParameterValue(
            parameter=MockParameter(name="gov.irs.credits.eitc.max.0"),
            value=600,
            start_date=date(2024, 1, 1),  # This one is valid
        ),
    ]
)

INVALID_ENTRIES_POLICY_EXPECTED = {
    "gov.irs.credits.eitc.max.0": {"2024-01-01": 600}
}


# =============================================================================
# Test data for _merge_reform_dicts
# =============================================================================

REFORM_DICT_1 = {
    "gov.irs.credits.ctc.amount.base": {"2024-01-01": 2000},
    "gov.irs.income.bracket.rates.1": {"2024-01-01": 0.10},
}

REFORM_DICT_2 = {
    "gov.irs.credits.ctc.amount.base": {"2024-01-01": 3000},  # Overwrites
    "gov.irs.credits.eitc.max.0": {"2024-01-01": 600},  # New param
}

MERGED_EXPECTED = {
    "gov.irs.credits.ctc.amount.base": {"2024-01-01": 3000},  # From reform2
    "gov.irs.income.bracket.rates.1": {"2024-01-01": 0.10},  # From reform1
    "gov.irs.credits.eitc.max.0": {"2024-01-01": 600},  # From reform2
}

REFORM_DICT_3 = {
    "gov.irs.credits.ctc.amount.base": {
        "2024-01-01": 2500,
        "2025-01-01": 2700,
    },
}

REFORM_DICT_4 = {
    "gov.irs.credits.ctc.amount.base": {
        "2025-01-01": 3000,  # Overwrites 2025 date
        "2026-01-01": 3500,  # New date
    },
}

MERGED_MULTI_DATE_EXPECTED = {
    "gov.irs.credits.ctc.amount.base": {
        "2024-01-01": 2500,  # From reform3
        "2025-01-01": 3000,  # From reform4 (overwrites)
        "2026-01-01": 3500,  # From reform4 (new)
    },
}


# =============================================================================
# Test data for household calculation policy conversion
# =============================================================================

# Policy data as it comes from the API (stored in database)
HOUSEHOLD_POLICY_DATA = {
    "parameter_values": [
        {
            "parameter_name": "gov.irs.credits.ctc.amount.base",
            "value": 3000,
            "start_date": "2024-01-01",
        },
        {
            "parameter_name": "gov.irs.credits.ctc.refundable.fully_refundable",
            "value": True,
            "start_date": "2024-01-01",
        },
    ]
}

HOUSEHOLD_POLICY_DATA_EXPECTED = {
    "gov.irs.credits.ctc.amount.base": {"2024-01-01": 3000},
    "gov.irs.credits.ctc.refundable.fully_refundable": {"2024-01-01": True},
}

# Policy data with ISO datetime strings
HOUSEHOLD_POLICY_DATA_DATETIME = {
    "parameter_values": [
        {
            "parameter_name": "gov.irs.credits.ctc.amount.base",
            "value": 3000,
            "start_date": "2024-01-01T00:00:00.000Z",
        },
    ]
}

HOUSEHOLD_POLICY_DATA_DATETIME_EXPECTED = {
    "gov.irs.credits.ctc.amount.base": {"2024-01-01": 3000},
}

# Empty policy data
HOUSEHOLD_EMPTY_POLICY_DATA = {"parameter_values": []}

# None policy data
HOUSEHOLD_NONE_POLICY_DATA = None

# Policy data with missing fields
HOUSEHOLD_INCOMPLETE_POLICY_DATA = {
    "parameter_values": [
        {
            "parameter_name": None,  # Missing
            "value": 3000,
            "start_date": "2024-01-01",
        },
        {
            "parameter_name": "gov.irs.credits.ctc.amount.base",
            "value": 3000,
            "start_date": None,  # Missing
        },
        {
            "parameter_name": "gov.irs.credits.eitc.max.0",
            "value": 600,
            "start_date": "2024-01-01",  # Valid
        },
    ]
}

HOUSEHOLD_INCOMPLETE_POLICY_DATA_EXPECTED = {
    "gov.irs.credits.eitc.max.0": {"2024-01-01": 600},
}
