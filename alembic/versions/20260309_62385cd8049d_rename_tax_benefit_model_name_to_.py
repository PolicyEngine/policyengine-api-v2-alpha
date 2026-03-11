"""rename_tax_benefit_model_name_to_country_id

Revision ID: 62385cd8049d
Revises: 886921687770
Create Date: 2026-03-09 16:48:30.899791

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = '62385cd8049d'
down_revision: Union[str, Sequence[str], None] = '886921687770'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: rename tax_benefit_model_name → country_id with data migration."""
    # 1. Add country_id columns (nullable initially)
    op.add_column('households', sa.Column('country_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('household_jobs', sa.Column('country_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True))

    # 2. Populate country_id from tax_benefit_model_name
    op.execute("""
        UPDATE households SET country_id = CASE
            WHEN tax_benefit_model_name LIKE '%_us' OR tax_benefit_model_name LIKE '%-us' THEN 'us'
            WHEN tax_benefit_model_name LIKE '%_uk' OR tax_benefit_model_name LIKE '%-uk' THEN 'uk'
            ELSE 'us'
        END
    """)
    op.execute("""
        UPDATE household_jobs SET country_id = CASE
            WHEN tax_benefit_model_name LIKE '%_us' OR tax_benefit_model_name LIKE '%-us' THEN 'us'
            WHEN tax_benefit_model_name LIKE '%_uk' OR tax_benefit_model_name LIKE '%-uk' THEN 'uk'
            ELSE 'us'
        END
    """)

    # 3. Make country_id non-nullable
    op.alter_column('households', 'country_id', nullable=False)
    op.alter_column('household_jobs', 'country_id', nullable=False)

    # 4. Drop old columns
    op.drop_column('households', 'tax_benefit_model_name')
    op.drop_column('household_jobs', 'tax_benefit_model_name')


def downgrade() -> None:
    """Downgrade schema: restore tax_benefit_model_name from country_id."""
    # 1. Re-add tax_benefit_model_name columns (nullable initially)
    op.add_column('households', sa.Column('tax_benefit_model_name', sa.VARCHAR(), nullable=True))
    op.add_column('household_jobs', sa.Column('tax_benefit_model_name', sa.VARCHAR(), nullable=True))

    # 2. Populate from country_id
    op.execute("UPDATE households SET tax_benefit_model_name = 'policyengine_' || country_id")
    op.execute("UPDATE household_jobs SET tax_benefit_model_name = 'policyengine_' || country_id")

    # 3. Make non-nullable
    op.alter_column('households', 'tax_benefit_model_name', nullable=False)
    op.alter_column('household_jobs', 'tax_benefit_model_name', nullable=False)

    # 4. Drop country_id columns
    op.drop_column('households', 'country_id')
    op.drop_column('household_jobs', 'country_id')
