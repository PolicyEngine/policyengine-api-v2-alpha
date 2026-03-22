"""Utility functions for household axes (earnings variation) support.

Axes allow varying a person's variable (e.g. employment_income) across a
linspace range, replicating all entities so the simulation covers the full
sweep in a single run.
"""

from __future__ import annotations

import numpy as np


def validate_axes(axes: list[list[dict]], n_people: int) -> None:
    """Validate axes specification.

    Args:
        axes: List of axis groups. Each group is a list of axis dicts with
              keys: name, min, max, count, index.
        n_people: Number of people in the household.

    Raises:
        ValueError: If axes spec is invalid.
    """
    if len(axes) == 0:
        raise ValueError("axes must contain exactly 1 axis group, got 0")
    if len(axes) > 1:
        raise ValueError(f"axes must contain exactly 1 axis group, got {len(axes)}")

    group = axes[0]
    if len(group) == 0:
        raise ValueError("Axis group must contain at least one axis")

    counts = set()
    for axis in group:
        name = axis.get("name", "")
        if not name or not isinstance(name, str):
            raise ValueError("Each axis must have a non-empty 'name' string")

        min_val = axis.get("min")
        max_val = axis.get("max")
        if not isinstance(min_val, (int, float)):
            raise ValueError(f"Axis '{name}': 'min' must be numeric")
        if not isinstance(max_val, (int, float)):
            raise ValueError(f"Axis '{name}': 'max' must be numeric")

        count = axis.get("count")
        if not isinstance(count, int) or count < 2 or count > 1000:
            raise ValueError(
                f"Axis '{name}': 'count' must be an integer between 2 and 1000"
            )

        index = axis.get("index", 0)
        if not isinstance(index, int) or index < 0 or index >= n_people:
            raise ValueError(f"Axis '{name}': 'index' must be in [0, {n_people})")

        counts.add(count)

    if len(counts) > 1:
        raise ValueError(
            f"All parallel axes in a group must have the same count, got {counts}"
        )


def expand_dataframes_for_axes(
    axes: list[list[dict]],
    person_data: dict[str, list],
    entity_datas: dict[str, dict[str, list]],
    person_entity_id_keys: dict[str, str],
) -> tuple[dict[str, list], dict[str, dict[str, list]], int]:
    """Expand person and entity data for axes simulation.

    Args:
        axes: Validated axes spec (exactly 1 group).
        person_data: Dict of column_name -> list of values for persons.
        entity_datas: Dict of entity_name -> {column_name -> list of values}.
            e.g. {"benunit": {"benunit_id": [0], ...}, "household": {...}}
        person_entity_id_keys: Mapping from entity_name to the FK column in
            person_data. e.g. {"benunit": "person_benunit_id", "household": "person_household_id"}

    Returns:
        (expanded_person_data, expanded_entity_datas, axis_count)
    """
    group = axes[0]
    axis_count = group[0]["count"]
    n_people = len(person_data["person_id"])

    # Replicate person rows: each person repeated axis_count times
    expanded_person = {}
    for col, values in person_data.items():
        expanded = []
        for val in values:
            expanded.extend([val] * axis_count)
        expanded_person[col] = expanded

    # Update person IDs to 0..n_people*axis_count-1
    expanded_person["person_id"] = list(range(n_people * axis_count))

    # Set all weights to 1.0
    if "person_weight" in expanded_person:
        expanded_person["person_weight"] = [1.0] * (n_people * axis_count)

    # Replicate entity rows and update IDs
    expanded_entities = {}
    for entity_name, entity_data in entity_datas.items():
        n_entities = len(next(iter(entity_data.values())))
        expanded_entity = {}
        for col, values in entity_data.items():
            expanded = []
            for val in values:
                expanded.extend([val] * axis_count)
            expanded_entity[col] = expanded

        # Update entity IDs to 0..n_entities*axis_count-1
        id_col = f"{entity_name}_id"
        if id_col in expanded_entity:
            expanded_entity[id_col] = list(range(n_entities * axis_count))

        # Set entity weights to 1.0
        weight_col = f"{entity_name}_weight"
        if weight_col in expanded_entity:
            expanded_entity[weight_col] = [1.0] * (n_entities * axis_count)

        expanded_entities[entity_name] = expanded_entity

    # Update person-to-entity FK mappings
    # Original person p pointing to entity e -> copy at position p*axis_count+i
    # should point to entity e*axis_count+i
    for entity_name, fk_col in person_entity_id_keys.items():
        if fk_col in expanded_person:
            original_fks = person_data[fk_col]
            new_fks = []
            for p_idx in range(n_people):
                orig_entity_id = original_fks[p_idx]
                for i in range(axis_count):
                    new_fks.append(int(orig_entity_id) * axis_count + i)
            expanded_person[fk_col] = new_fks

    # Apply linspace values for each axis in the group
    for axis in group:
        var_name = axis["name"]
        min_val = axis["min"]
        max_val = axis["max"]
        count = axis["count"]
        index = axis.get("index", 0)

        linspace_values = np.linspace(min_val, max_val, count).tolist()

        # Create column if it doesn't exist
        if var_name not in expanded_person:
            expanded_person[var_name] = [0.0] * (n_people * axis_count)

        # Set varied variable on target person's copies
        # Target person's copies are at positions index*axis_count .. index*axis_count+count-1
        start = index * axis_count
        for i in range(count):
            expanded_person[var_name][start + i] = linspace_values[i]

    return expanded_person, expanded_entities, axis_count


def reshape_axes_output(
    result: dict[str, list],
    n_original: dict[str, int],
    axis_count: int,
) -> dict[str, list]:
    """Reshape flat simulation output back into axes format.

    Groups axis_count consecutive rows per original entity into a single dict
    with array values.

    Args:
        result: Standard result dict like {"person": [{var: scalar}, ...]}
            with n_original * axis_count rows per entity.
        n_original: Dict of entity_name -> original count before expansion.
            e.g. {"person": 1, "benunit": 1, "household": 1}
        axis_count: Number of axis steps.

    Returns:
        Dict with same structure but array values per variable.
        e.g. {"person": [{"employment_income": [0, 500, ...]}]}
    """
    reshaped = {}
    for entity_name, rows in result.items():
        if not isinstance(rows, list):
            reshaped[entity_name] = rows
            continue

        orig_count = n_original.get(entity_name)
        if orig_count is None or len(rows) != orig_count * axis_count:
            # Unknown entity or mismatched row count - pass through unchanged
            reshaped[entity_name] = rows
            continue

        grouped = []
        for orig_idx in range(orig_count):
            start = orig_idx * axis_count
            end = start + axis_count
            chunk = rows[start:end]

            # Merge chunk into single dict with arrays
            merged = {}
            if chunk:
                for var in chunk[0]:
                    merged[var] = [row[var] for row in chunk]
            grouped.append(merged)

        reshaped[entity_name] = grouped

    return reshaped
