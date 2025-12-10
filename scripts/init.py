"""Initialise Supabase: reset database, recreate tables, buckets, and permissions.

This script performs a complete reset of the Supabase instance:
1. Drops and recreates the public schema (all tables)
2. Deletes and recreates the storage bucket
3. Creates all tables from SQLModel definitions
4. Applies RLS policies and storage permissions
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rich.console import Console
from rich.panel import Panel
from sqlmodel import SQLModel, create_engine

# Import all models to register them with SQLModel.metadata
from policyengine_api import models  # noqa: F401
from policyengine_api.config.settings import settings
from policyengine_api.services.storage import get_service_role_client

console = Console()

MIGRATIONS_DIR = Path(__file__).parent.parent / "supabase" / "migrations"


def reset_storage_bucket():
    """Delete and recreate the storage bucket."""
    console.print("[bold blue]Resetting storage bucket...")

    try:
        supabase = get_service_role_client()
        bucket_name = settings.storage_bucket

        # Try to delete the bucket (will fail if it doesn't exist)
        try:
            # First empty the bucket
            files = supabase.storage.from_(bucket_name).list()
            if files:
                file_paths = [f["name"] for f in files]
                supabase.storage.from_(bucket_name).remove(file_paths)
                console.print(f"  Removed {len(file_paths)} files")

            # Delete the bucket
            supabase.storage.delete_bucket(bucket_name)
            console.print(f"  Deleted bucket '{bucket_name}'")
        except Exception:
            console.print(f"  Bucket '{bucket_name}' does not exist, creating fresh")

        # Create the bucket
        supabase.storage.create_bucket(bucket_name, options={"public": True})
        console.print(f"[green]✓[/green] Created bucket '{bucket_name}'")

    except Exception as e:
        console.print(f"[yellow]⚠ Warning with storage bucket: {e}[/yellow]")


def reset_database():
    """Drop and recreate all tables."""
    console.print("[bold blue]Resetting database...")

    engine = create_engine(settings.database_url, echo=False)

    # Drop and recreate public schema
    console.print("  Dropping public schema...")
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP SCHEMA public CASCADE")
        conn.exec_driver_sql("CREATE SCHEMA public")
        conn.exec_driver_sql("GRANT ALL ON SCHEMA public TO postgres")
        conn.exec_driver_sql("GRANT ALL ON SCHEMA public TO public")

    # Create all tables from SQLModel
    console.print("  Creating tables...")
    SQLModel.metadata.create_all(engine)

    tables = list(SQLModel.metadata.tables.keys())
    console.print(f"[green]✓[/green] Created {len(tables)} tables:")
    for table in sorted(tables):
        console.print(f"    {table}")

    return engine


def apply_storage_policies(engine):
    """Apply storage bucket policies."""
    console.print("[bold blue]Applying storage policies...")

    sql = """
    -- Create storage bucket (if not exists via SQL)
    INSERT INTO storage.buckets (id, name, public)
    VALUES ('datasets', 'datasets', true)
    ON CONFLICT (id) DO UPDATE SET public = true;

    -- Drop existing policies to recreate them cleanly
    DROP POLICY IF EXISTS "Allow authenticated uploads" ON storage.objects;
    DROP POLICY IF EXISTS "Allow authenticated downloads" ON storage.objects;
    DROP POLICY IF EXISTS "Allow service role full access" ON storage.objects;
    DROP POLICY IF EXISTS "Allow public downloads" ON storage.objects;

    -- Allow authenticated uploads
    CREATE POLICY "Allow authenticated uploads"
    ON storage.objects FOR INSERT
    TO authenticated
    WITH CHECK (bucket_id = 'datasets');

    -- Allow authenticated downloads
    CREATE POLICY "Allow authenticated downloads"
    ON storage.objects FOR SELECT
    TO authenticated
    USING (bucket_id = 'datasets');

    -- Allow public downloads (for anon access)
    CREATE POLICY "Allow public downloads"
    ON storage.objects FOR SELECT
    TO anon
    USING (bucket_id = 'datasets');

    -- Allow service role full access
    CREATE POLICY "Allow service role full access"
    ON storage.objects FOR ALL
    TO service_role
    USING (bucket_id = 'datasets');
    """

    conn = engine.raw_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        conn.commit()
        console.print("[green]✓[/green] Storage policies applied")
    except Exception as e:
        console.print(f"[yellow]⚠ Warning applying storage policies: {e}[/yellow]")
    finally:
        conn.close()


def apply_rls_policies(engine):
    """Apply row-level security policies to all tables."""
    console.print("[bold blue]Applying RLS policies...")

    tables = [
        "datasets",
        "dataset_versions",
        "simulations",
        "policies",
        "dynamics",
        "aggregates",
        "change_aggregates",
        "tax_benefit_models",
        "tax_benefit_model_versions",
        "variables",
        "parameters",
        "parameter_values",
    ]

    # Read-only tables (public can read, only service role can write)
    readonly_tables = [
        "tax_benefit_models",
        "tax_benefit_model_versions",
        "variables",
        "parameters",
        "parameter_values",
        "datasets",
        "dataset_versions",
    ]

    # User-writable tables
    user_writable_tables = [
        "simulations",
        "policies",
        "dynamics",
    ]

    # Read-only results tables
    results_tables = [
        "aggregates",
        "change_aggregates",
    ]

    sql_parts = []

    # Enable RLS on all tables
    for table in tables:
        sql_parts.append(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")

    # Service role full access on all tables
    for table in tables:
        sql_parts.append(f"""
        DROP POLICY IF EXISTS "Service role full access" ON {table};
        CREATE POLICY "Service role full access" ON {table}
        FOR ALL TO service_role USING (true) WITH CHECK (true);
        """)

    # Public read access for read-only tables
    for table in readonly_tables:
        sql_parts.append(f"""
        DROP POLICY IF EXISTS "Public read access" ON {table};
        CREATE POLICY "Public read access" ON {table}
        FOR SELECT TO anon, authenticated USING (true);
        """)

    # User create/read for user-writable tables
    for table in user_writable_tables:
        sql_parts.append(f"""
        DROP POLICY IF EXISTS "Users can create" ON {table};
        CREATE POLICY "Users can create" ON {table}
        FOR INSERT TO anon, authenticated WITH CHECK (true);

        DROP POLICY IF EXISTS "Users can read" ON {table};
        CREATE POLICY "Users can read" ON {table}
        FOR SELECT TO anon, authenticated USING (true);
        """)

    # Read access for results tables
    for table in results_tables:
        sql_parts.append(f"""
        DROP POLICY IF EXISTS "Users can read" ON {table};
        CREATE POLICY "Users can read" ON {table}
        FOR SELECT TO anon, authenticated USING (true);
        """)

    sql = "\n".join(sql_parts)

    conn = engine.raw_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        conn.commit()
        console.print(f"[green]✓[/green] RLS policies applied to {len(tables)} tables")
    except Exception as e:
        console.print(f"[red]✗ Error applying RLS policies: {e}[/red]")
        raise
    finally:
        conn.close()


def main():
    """Run full Supabase initialisation."""
    console.print(
        Panel.fit(
            "[bold red]⚠ WARNING: This will DELETE ALL DATA[/bold red]\n"
            "This script resets the entire Supabase instance.",
            title="Supabase init",
        )
    )

    # Confirm unless running non-interactively
    if sys.stdin.isatty():
        response = console.input("\nType 'yes' to continue: ")
        if response.lower() != "yes":
            console.print("[yellow]Aborted[/yellow]")
            return

    console.print()

    # Reset storage bucket
    reset_storage_bucket()
    console.print()

    # Reset database and create tables
    engine = reset_database()
    console.print()

    # Apply storage policies
    apply_storage_policies(engine)
    console.print()

    # Apply RLS policies
    apply_rls_policies(engine)
    console.print()

    console.print(
        Panel.fit(
            "[bold green]✓ Supabase initialisation complete[/bold green]\n\n"
            "Next steps:\n"
            "  • Run [cyan]uv run python scripts/seed.py[/cyan] to seed data",
            title="Done",
        )
    )


if __name__ == "__main__":
    main()
