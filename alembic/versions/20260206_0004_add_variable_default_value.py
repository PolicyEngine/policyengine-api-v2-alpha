"""Add default_value to variables

Revision ID: 0004_var_default
Revises: 0003_param_idx
Create Date: 2026-02-06 03:30:00.000000

This migration adds a default_value column to the variables table.
The default_value is stored as JSON to handle different types (int, float, bool, str, etc.).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision: str = "0004_var_default"
down_revision: Union[str, Sequence[str], None] = "0003_param_idx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add default_value column to variables table."""
    op.add_column(
        "variables",
        sa.Column("default_value", JSON, nullable=True),
    )


def downgrade() -> None:
    """Remove default_value column from variables table."""
    op.drop_column("variables", "default_value")
