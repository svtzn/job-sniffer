"""Подписки на сохранённые фильтры: проверка новых вакансий и очередь уведомлений.

Никакого Telegram здесь нет — только «что найдено» и «что пора отправить».
Отправкой занимается app.telegram.notifier.

Жизненный цикл вакансии для фильтра (filter_vacancies.status):
    первая проверка после включения  -> seen      (ничего не шлём, только запоминаем)
    следующие проверки, новая        -> pending   (ждёт отправки)
    отправили                        -> notified
    «не интересно»                   -> hidden
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, time

from app.config import get_settings
from app.db.base import utcnow
from app.db.session import get_sessionmaker
from app.models import SavedFilter, Vacancy
from app.models.filter_vacancy import STATUS_PENDING, STATUS_SEEN
from app.repositories import filter_vacancies as fv_repo
from app.repositories import saved_filters as filters_repo
from app.repositories import vacancies as vacancies_repo
from app.services.filters import SearchFilters
from app.services.search import search_vacancies
from app.sniffers.schemas import Salary, VacancyData

logger = logging.getLogger(__name__)

# Одна страница HH на локацию: подписке нужно только свежее (сортировка по дате)
PER_LOCATION = 20


@dataclass
class CheckResult:
    filter_id: int
    chat_id: int
    new: int = 0  # сколько поставлено в очередь на отправку
    baseline: bool = False  # первая («тихая») проверка
    error: str | None = None


@dataclass
class PendingVacancy:
    """Вакансия к отправке + фильтры чата, под которые она подошла."""

    db_id: int
    vacancy: VacancyData
    filter_names: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- включение / выключение


async def set_subscribed(chat_id: int, filter_id: int, subscribed: bool) -> bool | None:
    """Включает/выключает подписку. None — фильтра нет (удалён или чужой)."""
    async with get_sessionmaker()() as session, session.begin():
        saved = await filters_repo.get(session, chat_id, filter_id)
        if saved is None:
            return None
        if saved.is_subscribed != subscribed:
            saved.is_subscribed = subscribed
            # После включения первая проверка снова «тихая»
            saved.last_checked_at = None
            if not subscribed:
                await fv_repo.drop_pending(session, filter_id)
        return subscribed


async def subscribed_filters() -> list[tuple[int, int]]:
    """(filter_id, chat_id) всех включённых подписок."""
    async with get_sessionmaker()() as session:
        return [(f.id, f.chat_id) for f in await filters_repo.list_subscribed(session)]


# ---------------------------------------------------------------- проверка


async def check_filter(filter_id: int) -> CheckResult | None:
    """Ищет свежие вакансии по фильтру и ставит новые в очередь.

    Поиск идёт вне транзакции (браузер — долго), запись — одной транзакцией.
    """
    async with get_sessionmaker()() as session:
        saved = await session.get(SavedFilter, filter_id)
        if saved is None or not saved.is_subscribed:
            return None
        chat_id, params, baseline = saved.chat_id, dict(saved.params), saved.last_checked_at is None

    filters = SearchFilters.from_dict(params)
    outcome = await search_vacancies(filters, limit=PER_LOCATION * len(filters.locations), newest_first=True)

    async with get_sessionmaker()() as session, session.begin():
        saved = await session.get(SavedFilter, filter_id)
        if saved is None or not saved.is_subscribed or saved.params != params:
            # пока искали, фильтр удалили, выключили или поменяли — результат неактуален
            return None
        ids = await vacancies_repo.upsert_vacancies(session, outcome.vacancies)
        status = STATUS_SEEN if baseline else STATUS_PENDING
        added = await fv_repo.add_missing(session, filter_id, ids.values(), status)
        saved.last_checked_at = utcnow()

    result = CheckResult(filter_id=filter_id, chat_id=chat_id, baseline=baseline)
    if not baseline:
        result.new = len(added)
    logger.info(
        "Подписка %s: %s",
        filter_id,
        f"первая проверка, запомнено {len(added)}" if baseline else f"новых {len(added)}",
    )
    return result


# ---------------------------------------------------------------- очередь отправки


def vacancy_from_row(row: Vacancy) -> VacancyData:
    return VacancyData(
        id=row.external_id,
        title=row.title,
        url=row.url,
        source=row.source,
        employer=row.employer,
        employer_trusted=row.employer_trusted,
        employer_rating=row.employer_rating,
        salary=Salary(
            amount_from=row.salary_from,
            amount_to=row.salary_to,
            currency=row.salary_currency,
            gross=row.salary_gross,
            mode=row.salary_mode,
        ),
        experience=row.experience,
        work_formats=list(row.work_formats or []),
        employment_form=row.employment_form,
        area=row.area,
        address=row.address,
        published_at=row.published_at,
        responses_count=row.responses_count,
        is_internship=row.is_internship,
    )


async def pending_for_chat(chat_id: int) -> list[PendingVacancy]:
    """Очередь чата; вакансия под несколько фильтров — одна запись со всеми их названиями."""
    async with get_sessionmaker()() as session:
        rows = await fv_repo.pending_for_chat(session, chat_id)

    grouped: dict[int, PendingVacancy] = {}
    for vacancy, saved in rows:
        item = grouped.get(vacancy.id)
        if item is None:
            item = grouped[vacancy.id] = PendingVacancy(db_id=vacancy.id, vacancy=vacancy_from_row(vacancy))
        if saved.name not in item.filter_names:
            item.filter_names.append(saved.name)
    return list(grouped.values())


async def chats_with_pending() -> list[int]:
    async with get_sessionmaker()() as session:
        return await fv_repo.chats_with_pending(session)


async def mark_notified(chat_id: int, vacancy_db_ids: list[int]) -> None:
    async with get_sessionmaker()() as session, session.begin():
        await fv_repo.mark_notified(session, chat_id, vacancy_db_ids)


async def hide_vacancy(chat_id: int, vacancy_db_id: int) -> bool:
    async with get_sessionmaker()() as session, session.begin():
        return await fv_repo.hide(session, chat_id, vacancy_db_id) > 0


# ---------------------------------------------------------------- тихие часы


def parse_quiet_hours(spec: str) -> tuple[time, time] | None:
    """«23-8» / «23:30-07:00» -> (start, end). Пусто или ошибка -> None (выключено)."""
    spec = (spec or "").strip()
    if not spec or "-" not in spec:
        return None
    try:
        start, end = (_parse_time(part) for part in spec.split("-", 1))
    except ValueError:
        logger.warning("QUIET_HOURS=%r не разобран, тихие часы выключены", spec)
        return None
    return (start, end) if start != end else None


def _parse_time(value: str) -> time:
    value = value.strip()
    hours, _, minutes = value.partition(":")
    return time(int(hours) % 24, int(minutes or 0))


def is_quiet_now(now: datetime | None = None, spec: str | None = None) -> bool:
    """Тихие часы по локальному времени компьютера, где запущен бот."""
    window = parse_quiet_hours(get_settings().quiet_hours if spec is None else spec)
    if window is None:
        return False
    current = (now or datetime.now()).time()
    start, end = window
    if start < end:
        return start <= current < end
    return current >= start or current < end  # окно через полночь, например 23-8
