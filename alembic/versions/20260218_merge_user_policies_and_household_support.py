"""merge user_policies and household_support branches

Revision ID: merge_001
Revises: 0002_user_policies, a1b2c3d4e5f6
Create Date: 2026-02-18

Merge the two migration branches that diverged from the initial schema:
- 0002_user_policies: added user_policies table + policy.tax_benefit_model_id
- f419b5f4acba → a1b2c3d4e5f6: added household support + regions table

No schema changes — both branches modify independent tables.
"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "merge_001"
down_revision: tuple[str, str] = ("0002_user_policies", "a1b2c3d4e5f6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No schema changes — merge only."""
    pass


def downgrade() -> None:
    """No schema changes — merge only."""
    pass
