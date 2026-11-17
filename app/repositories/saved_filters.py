"""SQL по сохранённым фильтрам."""

from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SavedFilter


async def create(session: AsyncSession, chat_id: int, name: str, params: dict[str, Any]) -> SavedFilter:
    saved = SavedFilter(chat_id=chat_id, name=name, params=params)
    session.add(saved)
    await session.flush()
    return saved


async def get(session: AsyncSession, chat_id: int, filter_id: int) -> SavedFilter | None:
    # chat_id в условии — чтобы чужой фильтр нельзя было открыть подменой callback_data
    stmt = select(SavedFilter).where(SavedFilter.id == filter_id, SavedFilter.chat_id == chat_id)
    return await session.scalar(stmt)


async def list_for_chat(session: AsyncSession, chat_id: int) -> list[SavedFilter]:
    stmt = select(SavedFilter).where(SavedFilter.chat_id == chat_id).order_by(SavedFilter.created_at, SavedFilter.id)
    return list(await session.scalars(stmt))


async def count_for_chat(session: AsyncSession, chat_id: int) -> int:
    stmt = select(func.count()).select_from(SavedFilter).where(SavedFilter.chat_id == chat_id)
    return await session.scalar(stmt) or 0


async def delete_one(session: AsyncSession, chat_id: int, filter_id: int) -> bool:
    stmt = delete(SavedFilter).where(SavedFilter.id == filter_id, SavedFilter.chat_id == chat_id)
    result = await session.execute(stmt)
    return result.rowcount > 0


async def list_subscribed(session: AsyncSession) -> list[SavedFilter]:
    stmt = select(SavedFilter).where(SavedFilter.is_subscribed.is_(True)).order_by(SavedFilter.chat_id, SavedFilter.id)
    return list(await session.scalars(stmt))
