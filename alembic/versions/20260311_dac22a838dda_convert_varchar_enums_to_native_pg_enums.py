"""convert_varchar_enums_to_native_pg_enums

Revision ID: dac22a838dda
Revises: f887cb5490bc
Create Date: 2026-03-11 01:37:08.928795

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'dac22a838dda'
down_revision: Union[str, Sequence[str], None] = 'f887cb5490bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert VARCHAR enum columns to native PostgreSQL enum types.

    The enum types may already exist with UPPERCASE values (created by
    SQLAlchemy's default create_all behavior). Since the columns are still
    VARCHAR, the types are unused — drop and recreate with lowercase values
    matching the data and the values_callable convention.
    """
    # Drop any pre-existing enum types (unused — columns are still VARCHAR)
    op.execute("DROP TYPE IF EXISTS regiontype CASCADE")
    op.execute("DROP TYPE IF EXISTS reporttype CASCADE")
    op.execute("DROP TYPE IF EXISTS deciletype CASCADE")

    # Create PG enum types with lowercase values
    op.execute("""
        CREATE TYPE regiontype AS ENUM (
            'national', 'country', 'state', 'congressional_district',
            'constituency', 'local_authority', 'city', 'place'
        )
    """)
    op.execute("""
        CREATE TYPE reporttype AS ENUM (
            'economy_comparison', 'household_comparison', 'household_single'
        )
    """)
    op.execute("CREATE TYPE deciletype AS ENUM ('income', 'wealth')")

    # Alter columns from VARCHAR to enum.
    # LOWER() handles any databases where values were previously uppercased.
    op.execute("""
        ALTER TABLE regions
        ALTER COLUMN region_type TYPE regiontype
        USING LOWER(region_type)::regiontype
    """)
    op.execute("""
        ALTER TABLE reports
        ALTER COLUMN report_type TYPE reporttype
        USING LOWER(report_type)::reporttype
    """)
    # decile_type has a VARCHAR default that must be dropped before type change
    op.execute("ALTER TABLE intra_decile_impacts ALTER COLUMN decile_type DROP DEFAULT")
    op.execute("""
        ALTER TABLE intra_decile_impacts
        ALTER COLUMN decile_type TYPE deciletype
        USING LOWER(decile_type)::deciletype
    """)
    op.execute("ALTER TABLE intra_decile_impacts ALTER COLUMN decile_type SET DEFAULT 'income'::deciletype")


def downgrade() -> None:
    """Revert native PG enum columns back to VARCHAR."""
    op.execute("""
        ALTER TABLE regions
        ALTER COLUMN region_type TYPE VARCHAR
        USING region_type::text
    """)
    op.execute("""
        ALTER TABLE reports
        ALTER COLUMN report_type TYPE VARCHAR
        USING report_type::text
    """)
    op.execute("""
        ALTER TABLE intra_decile_impacts
        ALTER COLUMN decile_type TYPE VARCHAR
        USING decile_type::text
    """)

    # Drop the PG enum types
    op.execute("DROP TYPE IF EXISTS regiontype")
    op.execute("DROP TYPE IF EXISTS reporttype")
    op.execute("DROP TYPE IF EXISTS deciletype")
