"""region_datasets_join_table_and_simulation_year

Revision ID: 886921687770
Revises: 963e91da9298
Create Date: 2026-03-03 18:56:13.551288

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "886921687770"
down_revision: Union[str, Sequence[str], None] = "963e91da9298"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create the region_datasets join table
    op.create_table(
        "region_datasets",
        sa.Column("region_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
        ),
        sa.ForeignKeyConstraint(
            ["region_id"],
            ["regions.id"],
        ),
        sa.PrimaryKeyConstraint("region_id", "dataset_id"),
    )

    # Migrate existing region->dataset links into the join table
    op.execute("""
        INSERT INTO region_datasets (region_id, dataset_id)
        SELECT id, dataset_id FROM regions
        WHERE dataset_id IS NOT NULL
    """)

    # Drop the old FK and column from regions
    op.drop_constraint(op.f("regions_dataset_id_fkey"), "regions", type_="foreignkey")
    op.drop_column("regions", "dataset_id")

    # Add year column to simulations
    op.add_column("simulations", sa.Column("year", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("simulations", "year")
    op.add_column(
        "regions",
        sa.Column("dataset_id", sa.UUID(), autoincrement=False, nullable=True),
    )

    # Migrate join table data back to the FK column (pick one dataset per region)
    op.execute("""
        UPDATE regions r
        SET dataset_id = rd.dataset_id
        FROM (
            SELECT DISTINCT ON (region_id) region_id, dataset_id
            FROM region_datasets
            ORDER BY region_id
        ) rd
        WHERE r.id = rd.region_id
    """)

    op.alter_column("regions", "dataset_id", nullable=False)
    op.create_foreign_key(
        op.f("regions_dataset_id_fkey"), "regions", "datasets", ["dataset_id"], ["id"]
    )
    op.drop_table("region_datasets")
