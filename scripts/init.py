"""Initialise Supabase database with tables, buckets, and permissions.

This script can run in two modes:
1. Init mode (default): Creates tables via Alembic, applies RLS policies
2. Reset mode (--reset): Drops everything and recreates from scratch (DESTRUCTIVE)

Usage:
    uv run python scripts/init.py          # Safe init (creates if not exists)
    uv run python scripts/init.py --reset  # Destructive reset (drops everything)

For local development after `supabase start`, use init mode.
For production, use init mode to ensure tables and policies exist.
Reset mode should only be used when you need a completely fresh database.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rich.console import Console
from rich.panel import Panel
from sqlmodel import create_engine

from policyengine_api.config.settings import settings
from policyengine_api.services.storage import get_service_role_client

console = Console()

PROJECT_ROOT = Path(__file__).parent.parent


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


def ensure_storage_bucket():
    """Ensure storage bucket exists (non-destructive)."""
    console.print("[bold blue]Ensuring storage bucket exists...")

    try:
        supabase = get_service_role_client()
        bucket_name = settings.storage_bucket

        # Try to get bucket info
        try:
            supabase.storage.get_bucket(bucket_name)
            console.print(f"[green]✓[/green] Bucket '{bucket_name}' exists")
        except Exception:
            # Bucket doesn't exist, create it
            supabase.storage.create_bucket(bucket_name, options={"public": True})
            console.print(f"[green]✓[/green] Created bucket '{bucket_name}'")

    except Exception as e:
        console.print(f"[yellow]⚠ Warning with storage bucket: {e}[/yellow]")


def reset_database():
    """Drop and recreate the public schema (DESTRUCTIVE)."""
    console.print("[bold red]Dropping database schema...")

    engine = create_engine(settings.database_url, echo=False)

    with engine.begin() as conn:
        conn.exec_driver_sql("DROP SCHEMA public CASCADE")
        conn.exec_driver_sql("CREATE SCHEMA public")
        conn.exec_driver_sql("GRANT ALL ON SCHEMA public TO postgres")
        conn.exec_driver_sql("GRANT ALL ON SCHEMA public TO public")

    console.print("[green]✓[/green] Schema dropped and recreated")
    return engine


def run_alembic_migrations():
    """Run Alembic migrations to create/update tables."""
    console.print("[bold blue]Running Alembic migrations...")

    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        console.print(f"[red]✗ Alembic migration failed:[/red]")
        console.print(result.stderr)
        raise RuntimeError("Alembic migration failed")

    console.print("[green]✓[/green] Alembic migrations complete")
    console.print(result.stdout)


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
        "reports",
        "decile_impacts",
        "program_statistics",
        "policies",
        "dynamics",
        "aggregates",
        "change_aggregates",
        "tax_benefit_models",
        "tax_benefit_model_versions",
        "variables",
        "parameters",
        "parameter_values",
        "users",
        "household_jobs",
        "households",
        "user_household_associations",
        "poverty",
        "inequality",
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
        "reports",
        "household_jobs",
        "households",
    ]

    # Read-only results tables
    results_tables = [
        "aggregates",
        "change_aggregates",
        "decile_impacts",
        "program_statistics",
        "poverty",
        "inequality",
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

    # User-household associations need special handling
    sql_parts.append("""
    DROP POLICY IF EXISTS "Users can manage own associations" ON user_household_associations;
    CREATE POLICY "Users can manage own associations" ON user_household_associations
    FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
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
    """Run Supabase initialisation."""
    reset_mode = "--reset" in sys.argv

    if reset_mode:
        console.print(
            Panel.fit(
                "[bold red]⚠ WARNING: This will DELETE ALL DATA[/bold red]\n"
                "This script will reset the entire Supabase instance.",
                title="Supabase RESET",
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

        # Drop database schema
        engine = reset_database()
        console.print()
    else:
        console.print(
            Panel.fit(
                "[bold blue]Initialising Supabase[/bold blue]\n"
                "This will create tables if they don't exist (safe/idempotent).\n"
                "Use [cyan]--reset[/cyan] flag to drop and recreate everything.",
                title="Supabase init",
            )
        )
        console.print()

        # Ensure storage bucket exists
        ensure_storage_bucket()
        console.print()

        engine = create_engine(settings.database_url, echo=False)

    # Run Alembic migrations to create/update tables
    run_alembic_migrations()
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
