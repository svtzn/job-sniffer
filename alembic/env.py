import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401  регистрирует модели в Base.metadata
from alembic import context
from app.config import get_settings
from app.db.base import Base
from app.db.session import resolve_database_url
from app.db.types import UTCDateTime

config = context.config
# При запуске из приложения логирование уже настроено — не перетираем его
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    return resolve_database_url(get_settings().database_url)


def _render_item(type_, obj, autogen_context):
    # UTCDateTime — питоновская обёртка; в схеме БД это обычный DateTime(timezone=True)
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime(timezone=True)"
    return False


def _configure(**kwargs) -> None:
    context.configure(
        target_metadata=target_metadata,
        render_item=_render_item,
        render_as_batch=True,  # SQLite не умеет ALTER COLUMN — Alembic пересоздаёт таблицу
        compare_type=True,
        **kwargs,
    )


def run_migrations_offline() -> None:
    _configure(url=_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    _configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(_url())
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
