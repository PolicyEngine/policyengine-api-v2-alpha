"""add_user_policies

Revision ID: 0002_user_policies
Revises: 36f9d434e95b
Create Date: 2026-02-05

This migration adds:
1. tax_benefit_model_id foreign key to policies table
2. user_policies table for user-policy associations

Note: user_id in user_policies is NOT a foreign key to users table.
It's a client-generated UUID stored in localStorage, allowing anonymous
users to save policies without authentication.
"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_user_policies"
down_revision: Union[str, Sequence[str], None] = "36f9d434e95b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add user_policies table and policy.tax_benefit_model_id."""
    # Add tax_benefit_model_id to policies table
    op.add_column(
        "policies", sa.Column("tax_benefit_model_id", sa.Uuid(), nullable=False)
    )
    op.create_index(
        op.f("ix_policies_tax_benefit_model_id"),
        "policies",
        ["tax_benefit_model_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_policies_tax_benefit_model_id",
        "policies",
        "tax_benefit_models",
        ["tax_benefit_model_id"],
        ["id"],
    )

    # Create user_policies table
    # Note: user_id is NOT a foreign key - it's a client-generated UUID from localStorage
    op.create_table(
        "user_policies",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("label", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_policies_policy_id"),
        "user_policies",
        ["policy_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_policies_user_id"), "user_policies", ["user_id"], unique=False
    )


def downgrade() -> None:
    """Remove user_policies table and policy.tax_benefit_model_id."""
    # Drop user_policies table
    op.drop_index(op.f("ix_user_policies_user_id"), table_name="user_policies")
    op.drop_index(op.f("ix_user_policies_policy_id"), table_name="user_policies")
    op.drop_table("user_policies")

    # Remove tax_benefit_model_id from policies
    op.drop_constraint(
        "fk_policies_tax_benefit_model_id", "policies", type_="foreignkey"
    )
    op.drop_index(op.f("ix_policies_tax_benefit_model_id"), table_name="policies")
    op.drop_column("policies", "tax_benefit_model_id")
