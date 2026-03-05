"""Shared utilities for seed scripts."""

import io
import logging
import sys
import warnings
from pathlib import Path

import logfire
from rich.console import Console
from sqlmodel import Session, create_engine

# Disable all SQLAlchemy and database logging
logging.basicConfig(level=logging.ERROR)
logging.getLogger("sqlalchemy").setLevel(logging.ERROR)
warnings.filterwarnings("ignore")

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from policyengine_api.config.settings import settings  # noqa: E402

# Configure logfire
if settings.logfire_token:
    logfire.configure(
        token=settings.logfire_token,
        environment=settings.logfire_environment,
        console=False,
    )

console = Console()


def get_session() -> Session:
    """Get database session with logging disabled."""
    engine = create_engine(settings.database_url, echo=False)
    return Session(engine)


def bulk_insert(session: Session, table: str, columns: list[str], rows: list[dict]):
    """Fast bulk insert using PostgreSQL COPY via StringIO."""
    if not rows:
        return

    # Get raw psycopg2 connection
    connection = session.connection()
    raw_conn = connection.connection.dbapi_connection
    cursor = raw_conn.cursor()

    # Build CSV-like data in memory
    output = io.StringIO()
    for row in rows:
        values = []
        for col in columns:
            val = row[col]
            if val is None:
                values.append("\\N")
            elif isinstance(val, str):
                # Escape special characters for COPY
                val = (
                    val.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n")
                )
                values.append(val)
            else:
                values.append(str(val))
        output.write("\t".join(values) + "\n")

    output.seek(0)

    # COPY is the fastest way to bulk load PostgreSQL
    cursor.copy_from(output, table, columns=columns, null="\\N")
    session.commit()
