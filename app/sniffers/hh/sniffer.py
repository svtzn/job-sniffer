# app/sniffers/hh/sniffer.py

from dataclasses import fields

from app.sniffers.base import BaseSniffer
from app.sniffers.hh.query import HHQuery
from app.sniffers.hh.parser import HHParser
from playwright.async_api import TimeoutError as PlaywrightTimeoutError


class HHSniffer(BaseSniffer):

    async def fetch_vacancies(self, query: HHQuery) -> list[dict]:
        all_vacancies: list[dict] = []
        page = 0

        while len(all_vacancies) < 100:
            page_query = HHQuery(**{
                field.name: (page if field.name == "page" else getattr(query, field.name))
                for field in fields(query)
            })
            html = await self._fetch_html(page_query)
            vacancies = HHParser().parse_vacancies(html)

            if not vacancies:
                break

            all_vacancies.extend(vacancies)
            page += 1

        return self._deduplicate(all_vacancies)

    def _deduplicate(self, vacancies: list[dict]) -> list[dict]:
        seen: set[tuple[str, ...]] = set()
        result: list[dict] = []

        for v in vacancies:
            title = v.get("title", "").lower().strip()
            if not title:
                continue

            employer = v.get("employer", "").lower().strip()
            if employer:
                key: tuple[str, ...] = (title, employer)
            else:
                key = (title,)

            if key in seen:
                continue
            seen.add(key)
            result.append(v)

        return result

    async def _fetch_html(self, query: HHQuery) -> str:
        url = query.get_url()

        try:
            await self.page.goto(url, wait_until=self.config.hh_wait_until)
        except PlaywrightTimeoutError:
            raise TimeoutError(f"Не удалось загрузить: {url}")

        await self._random_delay()
        return await self.page.content()
