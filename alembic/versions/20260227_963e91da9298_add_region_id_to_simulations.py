"""add region_id to simulations

Revision ID: 963e91da9298
Revises: 8d54837f0fcd
Create Date: 2026-02-27 22:47:47.740784

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "963e91da9298"
down_revision: Union[str, Sequence[str], None] = "8d54837f0fcd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("simulations", sa.Column("region_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(None, "simulations", "regions", ["region_id"], ["id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(None, "simulations", type_="foreignkey")
    op.drop_column("simulations", "region_id")
