"""Движок и фабрика сессий. Один движок на процесс."""

from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def resolve_database_url(url: str) -> str:
    """Относительный путь SQLite -> абсолютный от корня проекта (+ создаём папку)."""
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite" or not parsed.database or parsed.database == ":memory:":
        return url
    path = Path(parsed.database)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return parsed.set(database=str(path)).render_as_string(hide_password=False)


def _enable_sqlite_foreign_keys(dbapi_connection, _record) -> None:
    # В SQLite внешние ключи (и ON DELETE CASCADE) по умолчанию выключены
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        url = resolve_database_url(get_settings().database_url)
        _engine = create_async_engine(url)
        if _engine.dialect.name == "sqlite":
            event.listen(_engine.sync_engine, "connect", _enable_sqlite_foreign_keys)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = _sessionmaker = None
