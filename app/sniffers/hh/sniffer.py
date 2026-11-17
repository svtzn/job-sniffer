import logging
from dataclasses import replace

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.sniffers.base import BaseSniffer
from app.sniffers.hh.parser import HHParser
from app.sniffers.hh.query import HHQuery
from app.sniffers.schemas import SearchResult, VacancyData

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 100
# HH не отдаёт больше 2000 результатов (100 страниц), дальше листать бессмысленно
MAX_PAGES = 100


class HHSniffer(BaseSniffer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parser = HHParser()

    async def fetch_vacancies(self, query: HHQuery, limit: int = DEFAULT_LIMIT) -> SearchResult:
        """Листает выдачу HH, пока не наберёт ``limit`` уникальных вакансий
        или не кончатся страницы."""
        base_query = replace(query, base_url=query.base_url or self.config.hh_base_url)

        collected: list[VacancyData] = []
        seen_ids: set[str] = set()
        seen_keys: set[tuple[str, str]] = set()
        total_found: int | None = None
        page = base_query.page

        while len(collected) < limit and page < MAX_PAGES:
            html = await self._fetch_html(replace(base_query, page=page))
            result = self.parser.parse_page(html)
            if total_found is None:
                total_found = result.total_found

            if not result.vacancies:
                break

            for vacancy in result.vacancies:
                if not self._is_new(vacancy, seen_ids, seen_keys):
                    continue
                collected.append(vacancy)
                if len(collected) >= limit:
                    break

            if result.last_page is not None and page >= result.last_page:
                break
            page += 1

        logger.info("HH: собрано %s вакансий (всего на HH: %s)", len(collected), total_found)
        return SearchResult(vacancies=collected, total_found=total_found)

    @staticmethod
    def _is_new(vacancy: VacancyData, seen_ids: set[str], seen_keys: set[tuple[str, str]]) -> bool:
        """Дедупликация: по id (рекламные вакансии повторяются на каждой странице)
        и по паре «название + работодатель» (одна вакансия, размноженная по городам)."""
        if not vacancy.title or vacancy.id in seen_ids:
            return False
        key = (vacancy.title.lower().strip(), (vacancy.employer or "").lower().strip())
        if key in seen_keys:
            return False
        seen_ids.add(vacancy.id)
        seen_keys.add(key)
        return True

    async def _fetch_html(self, query: HHQuery) -> str:
        url = query.get_url()
        logger.debug("HH: GET %s", url)

        try:
            await self.page.goto(url, wait_until=self.config.hh_wait_until)
        except PlaywrightTimeoutError as e:
            raise TimeoutError(f"Не удалось загрузить: {url}") from e

        await self._random_delay()
        return await self.page.content()
