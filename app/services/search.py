"""Сервис поиска: SearchFilters -> запросы к источнику по каждой локации -> одна выдача.

Telegram-хендлеры ничего не знают про HHQuery и Playwright — только про
SearchFilters и SearchOutcome. Этот же сервис будет вызывать планировщик подписок.
"""

import asyncio
import logging
import math
import time
from dataclasses import dataclass, field

from app.config import get_settings
from app.db.session import get_sessionmaker
from app.repositories import vacancies as vacancies_repo
from app.services.filters import LocationRule, SearchFilters
from app.sniffers.hh.sniffer import HHSniffer
from app.sniffers.schemas import VacancyData

logger = logging.getLogger(__name__)

# Один браузер за раз: HH режет частые запросы, а Chromium ест ~300 МБ
_browser_lock = asyncio.Semaphore(1)


class SearchTimeoutError(TimeoutError):
    """Поиск целиком не уложился в SEARCH_TIMEOUT_SECONDS."""


@dataclass
class LocationOutcome:
    rule: LocationRule
    total_found: int | None  # сколько всего нашёл HH по этой локации
    fetched: int  # сколько загрузили по ней (до склейки)


@dataclass
class SearchOutcome:
    vacancies: list[VacancyData]
    locations: list[LocationOutcome]
    # vacancy.id -> индексы локаций (в filters.locations), под которые она попала
    matched_locations: dict[str, list[int]] = field(default_factory=dict)
    excluded: int = 0  # сколько отброшено по «исключить слова»

    @property
    def total_found(self) -> int | None:
        totals = [loc.total_found for loc in self.locations if loc.total_found is not None]
        return sum(totals) if totals else None


async def search_and_store(filters: SearchFilters, saved_filter_id: int | None = None) -> SearchOutcome:
    """Поиск + сохранение выдачи в БД.

    Если поиск шёл по сохранённому фильтру, найденные вакансии отмечаются
    как уже виденные по нему — подписка потом пришлёт только новые.
    Ошибка БД не должна лишать пользователя выдачи, поэтому она только логируется.
    """
    outcome = await search_vacancies(filters)
    try:
        await store_outcome(outcome, saved_filter_id)
    except Exception:
        logger.exception("Не удалось сохранить выдачу в БД")
    return outcome


async def store_outcome(outcome: SearchOutcome, saved_filter_id: int | None = None) -> dict[tuple[str, str], int]:
    async with get_sessionmaker()() as session, session.begin():
        ids = await vacancies_repo.upsert_vacancies(session, outcome.vacancies)
        if saved_filter_id is not None:
            await vacancies_repo.mark_seen(session, saved_filter_id, list(ids.values()))
    return ids


def search_is_busy() -> bool:
    return _browser_lock.locked()


async def search_vacancies(
    filters: SearchFilters, limit: int | None = None, newest_first: bool = False
) -> SearchOutcome:
    if not filters.text.strip():
        raise ValueError("Пустой поисковый запрос")

    settings = get_settings()
    limit = limit or settings.search_limit
    queries = filters.to_hh_queries(newest_first=newest_first)
    # общий бюджет делится между локациями, чтобы 2 локации не искались вдвое дольше
    per_location = max(1, math.ceil(limit / len(queries)))

    per_rule: list[list[VacancyData]] = []
    outcomes: list[LocationOutcome] = []
    async with _browser_lock:
        started = time.monotonic()
        try:
            # Предел только на сам поиск (не на ожидание очереди); браузер закроется в __aexit__
            async with asyncio.timeout(settings.search_timeout_seconds), HHSniffer(settings) as sniffer:
                for rule, query in zip(filters.locations, queries, strict=True):
                    logger.info("Поиск: %s (limit=%s)", query.get_url(), per_location)
                    result = await sniffer.fetch_vacancies(query, limit=per_location)
                    per_rule.append(result.vacancies)
                    outcomes.append(LocationOutcome(rule, result.total_found, len(result.vacancies)))
        except TimeoutError as e:
            if time.monotonic() - started < settings.search_timeout_seconds:
                raise  # таймаут загрузки страницы — у него своё сообщение
            raise SearchTimeoutError(
                f"HH не ответил за {settings.search_timeout_seconds} с — поиск прерван"
            ) from e
        logger.info("Поиск занял %.1f с", time.monotonic() - started)

    vacancies, matched = merge_results(per_rule)
    kept = [v for v in vacancies if not filters.is_excluded(v.title)]
    return SearchOutcome(
        vacancies=kept,
        locations=outcomes,
        matched_locations={v.id: matched[v.id] for v in kept},
        excluded=len(vacancies) - len(kept),
    )


def merge_results(per_rule: list[list[VacancyData]]) -> tuple[list[VacancyData], dict[str, list[int]]]:
    """Склеивает выдачи локаций без повторов.

    Повтор — тот же id или та же пара «название + работодатель» (одна вакансия,
    размноженная по городам). Для каждой вакансии запоминаются все локации,
    под которые она подошла.

    Порядок — чередование локаций (1-я из первой, 1-я из второй, 2-я из первой…),
    а не общая сортировка по дате: у «удалёнки по России» тысячи вакансий за
    последние часы, у своего города — десятки за недели, и при сортировке по дате
    свой город целиком уехал бы в конец выдачи. Внутри локации порядок HH
    (при нескольких локациях — по дате публикации) сохраняется.
    """
    by_key: dict[tuple[str, str], VacancyData] = {}
    matched: dict[str, list[int]] = {}
    order: list[VacancyData] = []

    for rank in range(max((len(vs) for vs in per_rule), default=0)):
        for idx, vacancies in enumerate(per_rule):
            if rank >= len(vacancies):
                continue
            v = vacancies[rank]
            key = (v.title.lower().strip(), (v.employer or "").lower().strip())
            kept = by_key.get(key)
            if kept is None:
                by_key[key] = v
                matched[v.id] = [idx]
                order.append(v)
            elif idx not in matched[kept.id]:
                matched[kept.id].append(idx)

    return order, matched
