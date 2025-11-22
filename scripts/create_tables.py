"""Create database tables from SQLModel definitions and apply SQL migrations.

This script creates all tables using SQLModel's metadata, ensuring the database
schema matches the Python model definitions exactly, then applies SQL migrations
for RLS policies and storage buckets.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlmodel import SQLModel, create_engine, text
from rich.console import Console

from policyengine_api.config.settings import settings
from policyengine_api.services.storage import get_service_role_client

# Import all models to register them with SQLModel.metadata
from policyengine_api.models import (
    Dataset,
    DatasetVersion,
    Dynamic,
    Parameter,
    ParameterValue,
    Policy,
    Simulation,
    TaxBenefitModel,
    TaxBenefitModelVersion,
    Variable,
    AggregateOutput,
    ChangeAggregate,
)

console = Console()

MIGRATIONS_DIR = Path(__file__).parent.parent / "supabase" / "migrations"


def clear_storage_bucket():
    """Clear all files from the storage bucket."""
    console.print("[bold blue]Clearing storage bucket...")

    try:
        supabase = get_service_role_client()

        # List all files in the bucket
        files = supabase.storage.from_(settings.storage_bucket).list()

        if not files:
            console.print("  Bucket is already empty")
            return

        # Delete each file
        file_paths = [f["name"] for f in files]
        for file_path in file_paths:
            supabase.storage.from_(settings.storage_bucket).remove([file_path])

        console.print(f"[green]✓ Removed {len(file_paths)} files from bucket")
    except Exception as e:
        console.print(f"[yellow]⚠ Warning clearing bucket: {e}")


def create_tables():
    """Create all tables from SQLModel definitions."""
    console.print("[bold blue]Creating database tables from SQLModel...")

    engine = create_engine(settings.database_url, echo=False)

    # Drop all tables first (clean slate)
    console.print("  Dropping existing tables...")
    SQLModel.metadata.drop_all(engine)

    # Create all tables
    console.print("  Creating tables...")
    SQLModel.metadata.create_all(engine)

    # List created tables
    tables = list(SQLModel.metadata.tables.keys())
    console.print(f"\n[green]✓ Created {len(tables)} tables:")
    for table in sorted(tables):
        console.print(f"  - {table}")

    return engine


def apply_migrations(engine):
    """Apply SQL migrations for RLS policies and storage."""
    console.print("\n[bold blue]Applying SQL migrations...")

    # Get sorted migration files
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

    if not migration_files:
        console.print("  [yellow]No migration files found")
        return

    for migration_file in migration_files:
        console.print(f"  Applying {migration_file.name}...")

        try:
            sql = migration_file.read_text()

            # Execute the entire SQL file as one transaction
            # Use raw connection to handle PostgreSQL-specific syntax like DO blocks
            conn = engine.raw_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(sql)
                conn.commit()
            finally:
                conn.close()

            console.print(f"  [green]✓ Applied {migration_file.name}")

        except Exception as e:
            console.print(f"  [yellow]⚠ Warning applying {migration_file.name}: {e}")
            # Continue with other migrations even if one fails

    console.print(f"\n[green]✓ Applied {len(migration_files)} migrations")


if __name__ == "__main__":
    clear_storage_bucket()
    engine = create_tables()
    apply_migrations(engine)
    console.print("\n[bold green]✓ Database setup complete!")

