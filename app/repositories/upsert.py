from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession


def insert_for(session: AsyncSession):
    """INSERT с поддержкой ON CONFLICT для текущей БД (SQLite сейчас, Postgres потом).

    У обоих диалектов одинаковый API: on_conflict_do_update / on_conflict_do_nothing.
    """
    dialect = session.bind.dialect.name
    if dialect == "sqlite":
        return sqlite.insert
    if dialect == "postgresql":
        return postgresql.insert
    raise NotImplementedError(f"Upsert не реализован для {dialect}")
