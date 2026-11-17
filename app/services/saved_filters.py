"""Сохранённые фильтры: CRUD для бота (а потом — для подписок).

Наружу отдаётся SavedFilterInfo с уже разобранным SearchFilters,
чтобы хендлеры не работали с ORM-объектами и JSON напрямую.
"""

from dataclasses import dataclass

from app.db.session import get_sessionmaker
from app.models import SavedFilter
from app.repositories import filter_vacancies as filter_vacancies_repo
from app.repositories import saved_filters as repo
from app.services.filters import SearchFilters

MAX_SAVED_FILTERS = 20
MAX_NAME_LENGTH = 64


class SavedFiltersLimitError(Exception):
    pass


@dataclass
class SavedFilterInfo:
    id: int
    name: str
    filters: SearchFilters
    is_subscribed: bool


def _info(saved: SavedFilter) -> SavedFilterInfo:
    return SavedFilterInfo(
        id=saved.id,
        name=saved.name,
        filters=SearchFilters.from_dict(saved.params),
        is_subscribed=saved.is_subscribed,
    )


def clean_name(name: str) -> str:
    name = " ".join(name.split())
    return name[:MAX_NAME_LENGTH] or "Без названия"


async def create(chat_id: int, filters: SearchFilters, name: str) -> SavedFilterInfo:
    async with get_sessionmaker()() as session, session.begin():
        if await repo.count_for_chat(session, chat_id) >= MAX_SAVED_FILTERS:
            raise SavedFiltersLimitError(f"Можно сохранить не больше {MAX_SAVED_FILTERS} фильтров")
        saved = await repo.create(session, chat_id, clean_name(name), filters.to_dict())
        return _info(saved)


async def get(chat_id: int, filter_id: int) -> SavedFilterInfo | None:
    async with get_sessionmaker()() as session:
        saved = await repo.get(session, chat_id, filter_id)
        return _info(saved) if saved else None


async def list_for_chat(chat_id: int) -> list[SavedFilterInfo]:
    async with get_sessionmaker()() as session:
        return [_info(s) for s in await repo.list_for_chat(session, chat_id)]


async def update_filters(chat_id: int, filter_id: int, filters: SearchFilters) -> SavedFilterInfo | None:
    async with get_sessionmaker()() as session, session.begin():
        saved = await repo.get(session, chat_id, filter_id)
        if saved is None:
            return None
        new_params = filters.to_dict()
        if SearchFilters.from_dict(saved.params).to_dict() != new_params:
            saved.params = new_params
            # Фильтр изменился — для подписки это новый поиск: следующая проверка снова
            # «тихая» (только запоминает выдачу), иначе пришла бы пачка старых вакансий.
            saved.last_checked_at = None
            await filter_vacancies_repo.drop_pending(session, saved.id)
        await session.flush()
        return _info(saved)


async def rename(chat_id: int, filter_id: int, name: str) -> SavedFilterInfo | None:
    async with get_sessionmaker()() as session, session.begin():
        saved = await repo.get(session, chat_id, filter_id)
        if saved is None:
            return None
        saved.name = clean_name(name)
        await session.flush()
        return _info(saved)


async def delete(chat_id: int, filter_id: int) -> bool:
    async with get_sessionmaker()() as session, session.begin():
        return await repo.delete_one(session, chat_id, filter_id)
