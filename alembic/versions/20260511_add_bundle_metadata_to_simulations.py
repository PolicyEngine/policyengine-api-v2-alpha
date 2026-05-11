"""add_bundle_metadata_to_simulations

Revision ID: add_bundle_metadata
Revises: fb663a6e28e4
Create Date: 2026-05-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_bundle_metadata"
down_revision: Union[str, Sequence[str], None] = "fb663a6e28e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "simulations",
        sa.Column(
            "bundle_metadata",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("simulations", "bundle_metadata")
