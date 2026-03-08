"""Reconstruct policyengine.py scoping strategy objects from DB columns.

Rather than storing serialized strategy objects in the database, we store
a simple filter_strategy string ('row_filter' or 'weight_replacement')
and reconstruct the full strategy object at runtime using the existing
filter_field, filter_value, and region_type columns plus a constant
config mapping for weight matrix locations.
"""

from policyengine.core.scoping_strategy import (
    RowFilterStrategy,
    ScopingStrategy,
    WeightReplacementStrategy,
)

# GCS locations for weight matrices, keyed by region type
WEIGHT_MATRIX_CONFIG: dict[str, dict[str, str]] = {
    "constituency": {
        "weight_matrix_bucket": "policyengine-uk-data-private",
        "weight_matrix_key": "parliamentary_constituency_weights.h5",
        "lookup_csv_bucket": "policyengine-uk-data-private",
        "lookup_csv_key": "constituencies_2024.csv",
    },
    "local_authority": {
        "weight_matrix_bucket": "policyengine-uk-data-private",
        "weight_matrix_key": "local_authority_weights.h5",
        "lookup_csv_bucket": "policyengine-uk-data-private",
        "lookup_csv_key": "local_authorities_2021.csv",
    },
}


def reconstruct_strategy(
    filter_strategy: str | None,
    filter_field: str | None,
    filter_value: str | None,
    region_type: str | None,
) -> ScopingStrategy | None:
    """Reconstruct a ScopingStrategy from DB columns.

    Args:
        filter_strategy: Strategy type ('row_filter' or 'weight_replacement').
        filter_field: The household variable name (for row_filter).
        filter_value: The value to match or region code.
        region_type: The region type (e.g., 'constituency', 'local_authority').

    Returns:
        A ScopingStrategy instance, or None if no strategy is needed.
    """
    if filter_strategy is None:
        return None

    if filter_strategy == "row_filter":
        if not filter_field or not filter_value:
            return None
        return RowFilterStrategy(
            variable_name=filter_field,
            variable_value=filter_value,
        )

    if filter_strategy == "weight_replacement":
        if not filter_value or not region_type:
            return None
        config = WEIGHT_MATRIX_CONFIG.get(region_type)
        if not config:
            raise ValueError(
                f"No weight matrix config for region type '{region_type}'. "
                f"Known types: {list(WEIGHT_MATRIX_CONFIG.keys())}"
            )
        return WeightReplacementStrategy(
            region_code=filter_value,
            **config,
        )

    raise ValueError(
        f"Unknown filter_strategy '{filter_strategy}'. "
        f"Expected 'row_filter' or 'weight_replacement'."
    )
