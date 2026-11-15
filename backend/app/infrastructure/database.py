"""Conexion a SQLite. La base la levanta uvicorn en el lifespan de la app."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

_engine: Engine | None = None


def _ensure_sqlite_dir(url: str) -> None:
    if not url.startswith("sqlite:///"):
        return
    raw = url.removeprefix("sqlite:///")
    Path(raw).parent.mkdir(parents=True, exist_ok=True)


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _ensure_sqlite_dir(settings.database_url)
        connect_args = (
            {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
        )
        _engine = create_engine(
            settings.database_url, connect_args=connect_args, pool_pre_ping=True
        )
    return _engine


def init_db() -> None:
    """Crea el archivo .db y las tablas si no existen."""
    from app.domain import models  # noqa: F401  (registra las tablas en el metadata)

    SQLModel.metadata.create_all(get_engine())
    _migrate_schema()


def _migrate_schema() -> None:
    """Migracion aditiva para bases creadas antes de agregar columnas.

    SQLite no permite ``ALTER TABLE ... ADD COLUMN IF NOT EXISTS``; se consulta
    ``PRAGMA table_info`` y se agrega solo lo que falta. No borra datos.
    """
    if not settings.database_url.startswith("sqlite"):
        return

    engine = get_engine()
    statements = [
        ("astronaut", "sex", "ALTER TABLE astronaut ADD COLUMN sex VARCHAR(8)"),
        ("astronaut", "birth_date", "ALTER TABLE astronaut ADD COLUMN birth_date DATE"),
    ]
    with engine.connect() as connection:
        for table, column, statement in statements:
            existing = {row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({table})")}
            if existing and column not in existing:
                connection.exec_driver_sql(statement)
        connection.commit()


def dispose_db() -> None:
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
