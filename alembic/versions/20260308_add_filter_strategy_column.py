"""add filter_strategy to regions and simulations

Revision ID: add_filter_strategy
Revises: 886921687770
Create Date: 2026-03-08

Adds filter_strategy column to regions and simulations tables.
Values are 'row_filter' or 'weight_replacement', indicating which
scoping strategy to use when running simulations for that region.

Data migration:
- Existing regions with filter_field != 'household_weight' -> 'row_filter'
- Existing regions with filter_field = 'household_weight' -> 'weight_replacement'
- Simulations inherit from their region's strategy
"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_filter_strategy"
down_revision: Union[str, Sequence[str], None] = "886921687770"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add filter_strategy column and backfill existing data."""
    # Add column to regions
    op.add_column(
        "regions",
        sa.Column("filter_strategy", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )

    # Add column to simulations
    op.add_column(
        "simulations",
        sa.Column("filter_strategy", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )

    # Backfill regions: set strategy based on existing filter_field
    conn = op.get_bind()

    # Regions with filter_field = 'household_weight' use weight replacement
    conn.execute(
        sa.text(
            "UPDATE regions SET filter_strategy = 'weight_replacement' "
            "WHERE filter_field = 'household_weight'"
        )
    )

    # Regions with other non-null filter_field use row filtering
    conn.execute(
        sa.text(
            "UPDATE regions SET filter_strategy = 'row_filter' "
            "WHERE filter_field IS NOT NULL AND filter_field != 'household_weight'"
        )
    )

    # Backfill simulations based on their region's strategy
    conn.execute(
        sa.text(
            "UPDATE simulations SET filter_strategy = regions.filter_strategy "
            "FROM regions "
            "WHERE simulations.region_id = regions.id "
            "AND regions.filter_strategy IS NOT NULL"
        )
    )


def downgrade() -> None:
    """Remove filter_strategy columns."""
    op.drop_column("simulations", "filter_strategy")
    op.drop_column("regions", "filter_strategy")
