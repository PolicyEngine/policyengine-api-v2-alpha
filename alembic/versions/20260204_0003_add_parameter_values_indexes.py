"""Add parameter_values indexes

Revision ID: 0003_param_idx
Revises: 0002_household
Create Date: 2026-02-04 02:20:00.000000

This migration adds performance indexes to the parameter_values table
for optimizing common query patterns.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_param_idx"
down_revision: Union[str, Sequence[str], None] = "0002_household"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add performance indexes to parameter_values."""
    # Composite index for the most common query pattern (filtering by both)
    op.create_index(
        "idx_parameter_values_parameter_policy",
        "parameter_values",
        ["parameter_id", "policy_id"],
    )

    # Single index on policy_id for filtering by policy alone
    op.create_index(
        "idx_parameter_values_policy",
        "parameter_values",
        ["policy_id"],
    )

    # Partial index for baseline values (policy_id IS NULL)
    # This optimizes the common "get current law values" query
    op.create_index(
        "idx_parameter_values_baseline",
        "parameter_values",
        ["parameter_id"],
        postgresql_where="policy_id IS NULL",
    )


def downgrade() -> None:
    """Remove parameter_values indexes."""
    op.drop_index("idx_parameter_values_baseline", "parameter_values")
    op.drop_index("idx_parameter_values_policy", "parameter_values")
    op.drop_index("idx_parameter_values_parameter_policy", "parameter_values")
