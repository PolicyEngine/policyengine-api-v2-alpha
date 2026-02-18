"""drop parent_report_id from reports

Revision ID: drop_parent_report
Revises: add_sim_filters
Create Date: 2026-02-18

Remove the unused self-referential parent_report_id foreign key from
the reports table. No code reads or writes this column.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "drop_parent_report"
down_revision: Union[str, Sequence[str], None] = "add_sim_filters"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop parent_report_id column and its FK constraint."""
    op.drop_constraint(
        "reports_parent_report_id_fkey", "reports", type_="foreignkey"
    )
    op.drop_column("reports", "parent_report_id")


def downgrade() -> None:
    """Re-add parent_report_id column and FK constraint."""
    op.add_column(
        "reports",
        sa.Column("parent_report_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "reports_parent_report_id_fkey",
        "reports",
        "reports",
        ["parent_report_id"],
        ["id"],
    )
