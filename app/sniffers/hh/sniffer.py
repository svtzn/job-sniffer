# app/sniffers/hh/sniffer.py

from app.sniffers.base import BaseSniffer
from app.sniffers.hh.query import HHQuery
from app.sniffers.hh.parser import HHParser
from playwright.async_api import TimeoutError as PlaywrightTimeoutError


class HHSniffer(BaseSniffer):

    async def fetch_vacancies(self, query: HHQuery) -> list[dict]:
        html = await self._fetch_html(query)
        return HHParser().parse_vacancies(html)

    async def _fetch_html(self, query: HHQuery) -> str:
        url = query.get_url()

        try:
            await self.page.goto(url, wait_until=self.config.hh_wait_until)
        except PlaywrightTimeoutError:
            raise TimeoutError(f"Не удалось загрузить: {url}")

        await self._random_delay()
        return await self.page.content()
