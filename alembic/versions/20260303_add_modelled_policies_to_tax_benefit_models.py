"""add modelled_policies to tax_benefit_models

Revision ID: add_modelled_policies
Revises: 963e91da9298
Create Date: 2026-03-03

This migration adds modelled_policies JSON column to tax_benefit_models table.
This field stores metadata about which policies are modeled for each country,
populated from country packages (policyengine-us, policyengine-uk) during seeding.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_modelled_policies"
down_revision: Union[str, Sequence[str], None] = "963e91da9298"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add modelled_policies column to tax_benefit_models table."""
    op.add_column(
        "tax_benefit_models",
        sa.Column("modelled_policies", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Remove modelled_policies column from tax_benefit_models table."""
    op.drop_column("tax_benefit_models", "modelled_policies")
