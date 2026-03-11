"""merge_parallel_branches

Revision ID: db93db748457
Revises: 0cbd97809414, add_variable_label, 67608331ee8a
Create Date: 2026-03-11 22:30:07.234183

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'db93db748457'
down_revision: Union[str, Sequence[str], None] = ('0cbd97809414', 'add_variable_label', '67608331ee8a')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
