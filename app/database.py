"""Database connection: engine, session factory and the base class for models."""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DATABASE_URL

# The engine manages the connections to PostgreSQL.
engine = create_engine(DATABASE_URL)

# Every request gets its own session (one unit of work with the database).
SessionLocal = sessionmaker(bind=engine, autoflush=False)

# All models (tables) inherit from this class.
Base = declarative_base()


def get_db():
    """FastAPI dependency: opens a session for one request and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
