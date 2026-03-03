"""Intra-decile income change computation.

Computes the distribution of income change categories within each income
decile, producing proportions for 5 categories per decile plus an overall
average row.
"""

from typing import Callable

import numpy as np

# The 5-category thresholds and labels (matching V1 structure)
BOUNDS = [-np.inf, -0.05, -1e-3, 1e-3, 0.05, np.inf]
CATEGORY_COLUMNS = [
    "lose_more_than_5pct",
    "lose_less_than_5pct",
    "no_change",
    "gain_less_than_5pct",
    "gain_more_than_5pct",
]


# --- Income change formula variants ---


# NOTE: This formula replicates V1's API (policyengine-api, endpoints/economy/
# compare.py lines 324-331). It appears to double-count the change because it
# adds absolute_change to the already-changed capped reform income:
#   capped_reform = max(reform, 1) + (reform - baseline)
# For the common case (both incomes > 1), this yields:
#   income_change = 2 * (reform - baseline) / baseline
# Kept here for reference while confirming with the team.
def _income_change_v1_original(
    baseline_income: np.ndarray,
    reform_income: np.ndarray,
) -> np.ndarray:
    absolute_change = reform_income - baseline_income
    capped_baseline = np.maximum(baseline_income, 1)
    capped_reform = np.maximum(reform_income, 1) + absolute_change
    return (capped_reform - capped_baseline) / capped_baseline


def _income_change_corrected(
    baseline_income: np.ndarray,
    reform_income: np.ndarray,
) -> np.ndarray:
    capped_baseline = np.maximum(baseline_income, 1)
    return (reform_income - baseline_income) / capped_baseline


# Strategy selector — change this to switch formulas
def get_income_change_formula() -> Callable[[np.ndarray, np.ndarray], np.ndarray]:
    return _income_change_corrected


# --- Main computation ---


def compute_intra_decile(
    baseline_household_data: dict[str, np.ndarray],
    reform_household_data: dict[str, np.ndarray],
) -> list[dict]:
    """Compute intra-decile impact proportions.

    Args:
        baseline_household_data: Dict with keys "household_net_income",
            "household_weight", "household_count_people",
            "household_income_decile" — all as raw numpy arrays.
        reform_household_data: Same keys for the reform simulation.

    Returns:
        List of 11 dicts (deciles 1-10 + overall as decile=0), each with
        keys: decile, lose_more_than_5pct, lose_less_than_5pct, no_change,
        gain_less_than_5pct, gain_more_than_5pct.
    """
    baseline_income = baseline_household_data["household_net_income"]
    reform_income = reform_household_data["household_net_income"]
    weights = baseline_household_data["household_weight"]
    people_per_hh = baseline_household_data["household_count_people"]
    decile = baseline_household_data["household_income_decile"]

    # People-weighted count per household
    people = people_per_hh * weights

    # Compute percentage income change
    formula = get_income_change_formula()
    income_change = formula(baseline_income, reform_income)

    # For each decile, compute proportion of people in each category
    rows = []
    for decile_num in range(1, 11):
        in_decile = decile == decile_num
        people_in_decile = people[in_decile].sum()

        proportions = {}
        for col, lower, upper in zip(CATEGORY_COLUMNS, BOUNDS[:-1], BOUNDS[1:]):
            in_category = (income_change > lower) & (income_change <= upper)
            in_both = in_decile & in_category

            if people_in_decile == 0:
                proportions[col] = 0.0
            else:
                proportions[col] = float(people[in_both].sum() / people_in_decile)

        rows.append({"decile": decile_num, **proportions})

    # Overall average: mean of the 10 decile proportions (matching V1)
    overall = {"decile": 0}
    for col in CATEGORY_COLUMNS:
        overall[col] = sum(r[col] for r in rows) / 10
    rows.append(overall)

    return rows
