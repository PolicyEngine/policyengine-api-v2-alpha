"""add regions table

Revision ID: a1b2c3d4e5f6
Revises: f419b5f4acba
Create Date: 2026-02-10 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f419b5f4acba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create regions table."""
    op.create_table(
        "regions",
        sa.Column("code", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("label", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("region_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("requires_filter", sa.Boolean(), nullable=False, default=False),
        sa.Column("filter_field", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("filter_value", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("parent_code", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("state_code", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("state_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("tax_benefit_model_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tax_benefit_model_id"],
            ["tax_benefit_models.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # Create unique constraint on (code, tax_benefit_model_id)
    op.create_index(
        "ix_regions_code_model",
        "regions",
        ["code", "tax_benefit_model_id"],
        unique=True,
    )


def downgrade() -> None:
    """Drop regions table."""
    op.drop_index("ix_regions_code_model", table_name="regions")
    op.drop_table("regions")
