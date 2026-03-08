from sqlmodel import Session, create_engine

from policyengine_api.config.settings import settings

engine = create_engine(settings.database_url, echo=settings.debug)


def get_session():
    """Get database session."""
    with Session(engine) as session:
        yield session
