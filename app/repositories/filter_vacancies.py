"""SQL по связке «фильтр ↔ вакансия» (статусы seen / pending / notified / hidden)."""

from collections.abc import Iterable

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.models import FilterVacancy, SavedFilter, Vacancy
from app.models.filter_vacancy import STATUS_HIDDEN, STATUS_NOTIFIED, STATUS_PENDING, STATUS_SEEN
from app.repositories.upsert import insert_for


async def add_missing(session: AsyncSession, filter_id: int, vacancy_ids: Iterable[int], status: str) -> list[int]:
    """Добавляет вакансии, которых ещё не было у фильтра, с указанным статусом.

    Уже известные не трогаются. Возвращает id реально добавленных — это и есть «новые».
    """
    ids = list(dict.fromkeys(vacancy_ids))
    if not ids:
        return []
    insert = insert_for(session)
    now = utcnow()
    stmt = (
        insert(FilterVacancy)
        .values([{"filter_id": filter_id, "vacancy_id": vid, "status": status, "first_seen_at": now} for vid in ids])
        .on_conflict_do_nothing(index_elements=[FilterVacancy.filter_id, FilterVacancy.vacancy_id])
        .returning(FilterVacancy.vacancy_id)
    )
    return list((await session.scalars(stmt)).all())


async def pending_for_chat(session: AsyncSession, chat_id: int) -> list[tuple[Vacancy, SavedFilter]]:
    """Ожидающие отправки вакансии чата: пары (вакансия, фильтр), старые первыми."""
    stmt = (
        select(Vacancy, SavedFilter)
        .join(FilterVacancy, FilterVacancy.vacancy_id == Vacancy.id)
        .join(SavedFilter, SavedFilter.id == FilterVacancy.filter_id)
        .where(SavedFilter.chat_id == chat_id, FilterVacancy.status == STATUS_PENDING)
        .order_by(FilterVacancy.first_seen_at, Vacancy.id, SavedFilter.id)
    )
    return [(row[0], row[1]) for row in (await session.execute(stmt)).all()]


async def chats_with_pending(session: AsyncSession) -> list[int]:
    stmt = (
        select(SavedFilter.chat_id)
        .join(FilterVacancy, FilterVacancy.filter_id == SavedFilter.id)
        .where(FilterVacancy.status == STATUS_PENDING)
        .distinct()
    )
    return list((await session.scalars(stmt)).all())


def _chat_filters(chat_id: int):
    return select(SavedFilter.id).where(SavedFilter.chat_id == chat_id).scalar_subquery()


async def mark_notified(session: AsyncSession, chat_id: int, vacancy_ids: Iterable[int]) -> None:
    ids = list(vacancy_ids)
    if not ids:
        return
    await session.execute(
        update(FilterVacancy)
        .where(
            FilterVacancy.filter_id.in_(_chat_filters(chat_id)),
            FilterVacancy.vacancy_id.in_(ids),
            FilterVacancy.status == STATUS_PENDING,
        )
        .values(status=STATUS_NOTIFIED, notified_at=utcnow())
    )


async def hide(session: AsyncSession, chat_id: int, vacancy_id: int) -> int:
    """«Не интересно»: скрывает вакансию во всех фильтрах чата. Возвращает число строк."""
    result = await session.execute(
        update(FilterVacancy)
        .where(FilterVacancy.filter_id.in_(_chat_filters(chat_id)), FilterVacancy.vacancy_id == vacancy_id)
        .values(status=STATUS_HIDDEN)
    )
    return result.rowcount


async def drop_pending(session: AsyncSession, filter_id: int) -> None:
    """При выключении подписки неотправленное больше не нужно — считаем его просто виденным."""
    await session.execute(
        update(FilterVacancy)
        .where(FilterVacancy.filter_id == filter_id, FilterVacancy.status == STATUS_PENDING)
        .values(status=STATUS_SEEN)
    )
