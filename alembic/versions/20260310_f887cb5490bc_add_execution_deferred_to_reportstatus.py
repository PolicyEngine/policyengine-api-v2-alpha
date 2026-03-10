"""add_execution_deferred_to_reportstatus

Revision ID: f887cb5490bc
Revises: 62385cd8049d
Create Date: 2026-03-10 21:27:32.072364

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f887cb5490bc'
down_revision: Union[str, Sequence[str], None] = '62385cd8049d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add EXECUTION_DEFERRED value to the reportstatus enum."""
    op.execute("ALTER TYPE reportstatus ADD VALUE IF NOT EXISTS 'EXECUTION_DEFERRED'")


def downgrade() -> None:
    """Downgrade: PostgreSQL does not support removing enum values.

    The 'EXECUTION_DEFERRED' value will remain in the enum type.
    To fully remove it, drop and recreate the type (requires migrating data).
    """
    pass
