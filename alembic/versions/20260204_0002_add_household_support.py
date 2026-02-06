"""Add household CRUD and impact analysis support

Revision ID: 0002_household
Revises: 0001_initial
Create Date: 2026-02-04

This migration adds support for:
- Storing household definitions (households table)
- User-household associations for saved households
- Household-based simulations (adds household_id to simulations)
- Household impact reports (adds report_type to reports)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_household"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add household support."""
    # ========================================================================
    # NEW TABLES
    # ========================================================================

    # Households (stored household definitions)
    op.create_table(
        "households",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tax_benefit_model_name", sa.String(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("household_data", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_households_model_name", "households", ["tax_benefit_model_name"]
    )
    op.create_index("idx_households_year", "households", ["year"])

    # User-household associations (many-to-many for saved households)
    # Note: user_id is a client-generated UUID stored in localStorage, not a foreign key
    op.create_table(
        "user_household_associations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("country_id", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "household_id"),
    )
    op.create_index(
        "idx_user_household_user", "user_household_associations", ["user_id"]
    )
    op.create_index(
        "idx_user_household_household", "user_household_associations", ["household_id"]
    )

    # ========================================================================
    # MODIFY SIMULATIONS TABLE
    # ========================================================================

    # Add simulation_type column (economy vs household)
    op.add_column(
        "simulations",
        sa.Column(
            "simulation_type",
            sa.String(),
            nullable=False,
            server_default="economy",
        ),
    )

    # Add household_id column (for household simulations)
    op.add_column(
        "simulations",
        sa.Column("household_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_simulations_household_id",
        "simulations",
        "households",
        ["household_id"],
        ["id"],
    )

    # Add household_result column (stores household calculation results)
    op.add_column(
        "simulations",
        sa.Column("household_result", sa.JSON(), nullable=True),
    )

    # Make dataset_id nullable (household simulations don't need a dataset)
    op.alter_column(
        "simulations",
        "dataset_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )

    # ========================================================================
    # MODIFY REPORTS TABLE
    # ========================================================================

    # Add report_type column (economy_comparison, household_impact, etc.)
    op.add_column(
        "reports",
        sa.Column("report_type", sa.String(), nullable=True),
    )


def downgrade() -> None:
    """Remove household support."""
    # ========================================================================
    # REVERT REPORTS TABLE
    # ========================================================================
    op.drop_column("reports", "report_type")

    # ========================================================================
    # REVERT SIMULATIONS TABLE
    # ========================================================================

    # Make dataset_id required again
    op.alter_column(
        "simulations",
        "dataset_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )

    # Remove household columns
    op.drop_column("simulations", "household_result")
    op.drop_constraint("fk_simulations_household_id", "simulations", type_="foreignkey")
    op.drop_column("simulations", "household_id")
    op.drop_column("simulations", "simulation_type")

    # ========================================================================
    # DROP NEW TABLES
    # ========================================================================
    op.drop_index("idx_user_household_household", "user_household_associations")
    op.drop_index("idx_user_household_user", "user_household_associations")
    op.drop_table("user_household_associations")

    op.drop_index("idx_households_year", "households")
    op.drop_index("idx_households_model_name", "households")
    op.drop_table("households")
