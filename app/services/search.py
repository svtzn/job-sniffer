"""Сервис поиска: фильтры пользователя -> запрос к источнику -> нормализованный результат.

Telegram-хендлеры ничего не знают про HHQuery и Playwright — только про
SearchFilters и SearchResult. Сюда же потом встанут матчер/скоринг/ИИ-оценка.
"""

import asyncio
import logging
from dataclasses import dataclass, field

from app.config import get_settings
from app.sniffers.hh.query import EmploymentForm, Experience, HHQuery, Label, WorkFormat
from app.sniffers.hh.sniffer import HHSniffer
from app.sniffers.schemas import SearchResult

logger = logging.getLogger(__name__)

# Регионы HH (area id). None — без ограничения по региону.
AREAS: dict[str, int | None] = {
    "Россия": 113,
    "Москва": 1,
    "Санкт-Петербург": 2,
    "Краснодар": 53,
    "Везде": None,
}
DEFAULT_AREA = "Россия"

# Один браузер за раз: HH режет частые запросы, а Chromium ест ~300 МБ
_browser_lock = asyncio.Semaphore(1)


@dataclass
class SearchFilters:
    text: str = ""
    work_formats: set[WorkFormat] = field(default_factory=set)
    employment_forms: set[EmploymentForm] = field(default_factory=set)
    experiences: set[Experience] = field(default_factory=set)
    area: str = DEFAULT_AREA
    only_with_salary: bool = False

    def copy(self) -> "SearchFilters":
        return SearchFilters(
            text=self.text,
            work_formats=set(self.work_formats),
            employment_forms=set(self.employment_forms),
            experiences=set(self.experiences),
            area=self.area,
            only_with_salary=self.only_with_salary,
        )

    def to_hh_query(self) -> HHQuery:
        return HHQuery(
            text=self.text.strip() or None,
            work_format=_sorted(self.work_formats),
            employment_form=_sorted(self.employment_forms),
            experience=_sorted(self.experiences),
            area=AREAS.get(self.area),
            label=(Label.with_salary,) if self.only_with_salary else (),
        )


def _sorted(values: set) -> tuple:
    # стабильный порядок -> стабильный URL (пригодится для кэша/подписок)
    return tuple(sorted(values, key=lambda v: v.value))


def search_is_busy() -> bool:
    return _browser_lock.locked()


async def search_vacancies(filters: SearchFilters, limit: int | None = None) -> SearchResult:
    if not filters.text.strip():
        raise ValueError("Пустой поисковый запрос")

    settings = get_settings()
    query = filters.to_hh_query()
    limit = limit or settings.search_limit

    async with _browser_lock:
        logger.info("Поиск: %s (limit=%s)", query.get_url(), limit)
        async with HHSniffer(settings) as sniffer:
            return await sniffer.fetch_vacancies(query, limit=limit)
