"""Merge heads dac22a and db93d

Revision ID: fb663a6e28e4
Revises: dac22a838dda, db93db748457
Create Date: 2026-03-16 23:28:57.151366

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "fb663a6e28e4"
down_revision: Union[str, Sequence[str], None] = ("dac22a838dda", "db93db748457")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
