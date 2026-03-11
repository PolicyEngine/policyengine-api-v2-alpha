"""Add label column to variables table

Revision ID: add_variable_label
Revises: 886921687770
Create Date: 2026-03-05

Variables now carry a human-readable label sourced from OpenFisca's
Variable.label class attribute (e.g. "Employment income"). Previously
labels were auto-generated on the frontend from the snake_case name.
"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_variable_label"
down_revision: Union[str, Sequence[str], None] = "886921687770"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add label column to variables table."""
    op.add_column(
        "variables",
        sa.Column("label", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )


def downgrade() -> None:
    """Remove label column from variables table."""
    op.drop_column("variables", "label")
