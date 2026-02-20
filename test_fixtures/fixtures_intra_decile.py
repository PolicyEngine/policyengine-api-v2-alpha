"""Fixtures for intra-decile impact tests."""

import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NUM_HOUSEHOLDS = 100
HOUSEHOLDS_PER_DECILE = NUM_HOUSEHOLDS // 10

# Each decile has 10 households; deciles 1-10
DECILES = np.repeat(np.arange(1, 11), HOUSEHOLDS_PER_DECILE).astype(float)

UNIFORM_WEIGHTS = np.ones(NUM_HOUSEHOLDS) * 100.0
UNIFORM_PEOPLE = np.full(NUM_HOUSEHOLDS, 2.0)

# Income change thresholds (matching intra_decile.py BOUNDS)
THRESHOLD_5PCT = 0.05
THRESHOLD_0_1PCT = 1e-3

CATEGORY_NAMES = [
    "lose_more_than_5pct",
    "lose_less_than_5pct",
    "no_change",
    "gain_less_than_5pct",
    "gain_more_than_5pct",
]

EXPECTED_ROW_COUNT = 11  # 10 deciles + 1 overall (decile=0)
EXPECTED_DECILE_NUMBERS = list(range(1, 11)) + [0]


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------


def make_baseline_income() -> np.ndarray:
    """Baseline incomes: decile N earns N * 10,000."""
    return DECILES * 10_000.0


def make_household_data(
    baseline_income: np.ndarray,
    reform_income: np.ndarray | None = None,
    weights: np.ndarray | None = None,
    people: np.ndarray | None = None,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Build baseline and reform household data dicts for compute_intra_decile."""
    if reform_income is None:
        reform_income = baseline_income.copy()
    if weights is None:
        weights = UNIFORM_WEIGHTS.copy()
    if people is None:
        people = UNIFORM_PEOPLE.copy()

    baseline = {
        "household_net_income": baseline_income,
        "household_weight": weights,
        "household_count_people": people,
        "household_income_decile": DECILES.copy(),
    }
    reform = {
        "household_net_income": reform_income,
        "household_weight": weights,
        "household_count_people": people,
        "household_income_decile": DECILES.copy(),
    }
    return baseline, reform


def make_single_household_arrays(
    baseline_val: float, reform_val: float
) -> tuple[np.ndarray, np.ndarray]:
    """Create single-element arrays for formula unit tests."""
    return np.array([baseline_val]), np.array([reform_val])
