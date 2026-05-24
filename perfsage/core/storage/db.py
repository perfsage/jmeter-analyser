"""SQLModel database engine and session management."""

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from perfsage.config import get_settings


def get_engine() -> Engine:
    """Return a SQLAlchemy engine configured from settings."""
    settings = get_settings()
    return create_engine(settings.database_url)


def create_db_and_tables() -> None:
    """Create all SQLModel tables if they don't exist."""
    engine = get_engine()
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    """Return a new database session (caller is responsible for closing)."""
    engine = get_engine()
    return Session(engine)
