from sqlmodel import Session, create_engine

from policyengine_api.config.settings import settings

engine = create_engine(settings.database_url, echo=settings.debug)

# Only instrument with logfire if configured
if settings.logfire_token:
    import logfire

    logfire.instrument_sqlalchemy(engine=engine)


def get_session():
    """Get database session."""
    with Session(engine) as session:
        yield session


def init_db():
    """Initialize database tables."""
    from sqlmodel import SQLModel

    SQLModel.metadata.create_all(engine)
