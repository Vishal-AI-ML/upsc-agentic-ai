"""Database engine/session setup (SQLAlchemy 2.0).

Multi-user data layer. Uses DATABASE_URL from settings:
  - Production: managed Postgres (Neon/Supabase), e.g.
      postgresql://user:pass@host/db?sslmode=require
  - Local fallback: SQLite file (no setup needed)
Swap DBs by changing DATABASE_URL only - no code change.
"""
import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src.core.config import settings

logger = logging.getLogger(__name__)

_db_url = settings.database_url or "sqlite:///./upsc_app.db"

# SQLite needs check_same_thread=False to work with FastAPI's threadpool.
_connect_args = {"check_same_thread": False} if _db_url.startswith("sqlite") else {}

engine = create_engine(_db_url, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


def get_db():
    """FastAPI dependency: yield a DB session and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _run_lightweight_migrations() -> None:
    """Add columns introduced after the initial release for existing DBs (no Alembic).

    Currently: users.email_verified. Existing users are grandfathered as verified
    so the new email-verification gate never locks out anyone already registered.
    """
    try:
        insp = inspect(engine)
        if "users" not in insp.get_table_names():
            return
        cols = {c["name"] for c in insp.get_columns("users")}
        if "email_verified" not in cols:
            is_sqlite = _db_url.startswith("sqlite")
            ddl = (
                "ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0"
                if is_sqlite else
                "ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT false"
            )
            grandfather = (
                "UPDATE users SET email_verified = 1" if is_sqlite
                else "UPDATE users SET email_verified = true"
            )
            with engine.begin() as conn:
                conn.execute(text(ddl))
                conn.execute(text(grandfather))
            logger.info("Migration: added users.email_verified (existing users grandfathered as verified)")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Lightweight migration check failed: {e}")


def init_db() -> None:
    """Create tables if missing. Imports models so they register on Base."""
    from src.core import models  # noqa: F401  (registers tables)
    Base.metadata.create_all(bind=engine)
    _run_lightweight_migrations()
    safe = _db_url.split("@")[-1] if "@" in _db_url else _db_url
    logger.info(f"Database ready: {safe}")
