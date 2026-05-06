"""
data/database.py — Engine, session factory, and FastAPI dependency.
"""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from config import get_settings
from data.models import Base

settings = get_settings()

# ── Engine ────────────────────────────────────────────────────────────────────
connect_args = {}
if settings.database_url.startswith("sqlite"):
    # SQLite needs this for multi-threaded use (FastAPI / tests)
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    pool_size=settings.db_pool_size if not settings.database_url.startswith("sqlite") else 1,
    max_overflow=settings.db_max_overflow if not settings.database_url.startswith("sqlite") else 0,
    connect_args=connect_args,
    echo=settings.debug,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ── Helpers ───────────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create all tables. In production use Alembic migrations instead."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """Context manager for use outside FastAPI (scripts, Airflow tasks)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
