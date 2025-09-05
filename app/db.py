"""Database setup (SQLAlchemy 2.x, sync engine)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """Declarative base class for ORM models."""


def _resolve_sqlite_url(url: str) -> URL | str:
    """
    Ensure SQLite path points to a project-local file and the directory exists.
    Keeps other URLs untouched.
    """
    if not url.startswith("sqlite:///"):
        return url  # Non-SQLite or already a full URL

    # Remove scheme and compute path relative to project root
    raw = url.removeprefix("sqlite:///")
    path = Path(raw)
    if not path.is_absolute():
        project_root = Path(__file__).resolve().parents[1]  # repo root (folder containing /app)
        path = (project_root / path).resolve()

    path.parent.mkdir(parents=True, exist_ok=True)
    return URL.create(drivername="sqlite", database=str(path))


database_url = _resolve_sqlite_url(settings.database_url)

connect_args: dict[str, Any] = {}
if (isinstance(database_url, str) and database_url.startswith("sqlite")) or (
    isinstance(database_url, URL) and database_url.get_backend_name() == "sqlite"
):
    connect_args = {"check_same_thread": False}

engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

if (isinstance(database_url, str) and database_url.startswith("sqlite")) or (
    isinstance(database_url, URL) and database_url.get_backend_name() == "sqlite"
):

    @event.listens_for(engine, "connect")
    def _sqlite_pragma(dbapi_connection, _) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


def get_session() -> Iterator:
    """Provide a DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
