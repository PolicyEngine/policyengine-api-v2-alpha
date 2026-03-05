"""add filter_field and filter_value to simulations

Revision ID: add_sim_filters
Revises: merge_001
Create Date: 2026-02-18

The Simulation model already has filter_field and filter_value fields
(used for regional economy simulations), but no migration added them
to the database. This brings the schema in line with the model.
"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_sim_filters"
down_revision: Union[str, Sequence[str], None] = "merge_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add filter_field and filter_value columns to simulations table."""
    op.add_column(
        "simulations",
        sa.Column("filter_field", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.add_column(
        "simulations",
        sa.Column("filter_value", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )


def downgrade() -> None:
    """Remove filter_field and filter_value columns from simulations table."""
    op.drop_column("simulations", "filter_value")
    op.drop_column("simulations", "filter_field")
