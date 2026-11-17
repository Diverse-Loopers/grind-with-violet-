"""
SQLAlchemy 2.0 database setup with SQLite.
Provides engine, session factory, Base class, and init_db().
"""

from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


engine = create_engine(
    settings.db_url,
    echo=False,
    connect_args={"check_same_thread": False, "timeout": 30},  # SQLite-specific with 30s busy timeout
    pool_pre_ping=True,
)


# Enable WAL mode and foreign keys for SQLite
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def get_db_context():
    """Context manager for standalone database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db() -> Session:  # type: ignore[misc]
    """FastAPI dependency that yields a DB session."""
    db = SessionLocal()
    try:
        yield db  # type: ignore[misc]
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Import models first so they register with Base."""
    # Import models so SQLAlchemy registers them on Base.metadata
    import app.models.instrument  # noqa: F401
    import app.models.signal  # noqa: F401
    import app.models.order  # noqa: F401
    import app.models.position  # noqa: F401
    import app.models.portfolio  # noqa: F401
    import app.models.backtest  # noqa: F401
    import app.models.risk_settings  # noqa: F401
    import app.models.ledger  # noqa: F401
    import app.coindcx.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Safe SQLite column migrations for existing databases
    with engine.connect() as conn:
        cursor = conn.connection.cursor()
        cursor.execute("PRAGMA table_info(backtest_runs)")
        cols = {row[1] for row in cursor.fetchall()}
        if cols:
            if "expectancy" not in cols:
                cursor.execute("ALTER TABLE backtest_runs ADD COLUMN expectancy REAL")
            if "benchmark_return_pct" not in cols:
                cursor.execute("ALTER TABLE backtest_runs ADD COLUMN benchmark_return_pct REAL")
            if "out_of_sample_return_pct" not in cols:
                cursor.execute("ALTER TABLE backtest_runs ADD COLUMN out_of_sample_return_pct REAL")
        conn.connection.commit()
