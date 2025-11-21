from sqlmodel import Session, create_engine
import logfire

from policyengine_api.config.settings import settings

engine = create_engine(settings.database_url, echo=settings.debug)
# SQLAlchemy introspects the database schema on startup by querying pg_catalog
# These queries are normal and only happen once per startup
logfire.instrument_sqlalchemy(engine=engine)


def get_session():
    """Get database session."""
    with Session(engine) as session:
        yield session


def init_db():
    """Initialize database tables."""
    from sqlmodel import SQLModel

    SQLModel.metadata.create_all(engine)
