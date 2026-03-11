"""add_adds_subtracts_to_variables

Revision ID: 0cbd97809414
Revises: 886921687770
Create Date: 2026-03-05 20:26:07.571012

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0cbd97809414'
down_revision: Union[str, Sequence[str], None] = '886921687770'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('variables', sa.Column('adds', sa.JSON(), nullable=True))
    op.add_column('variables', sa.Column('subtracts', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('variables', 'subtracts')
    op.drop_column('variables', 'adds')
