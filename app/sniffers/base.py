from app.config import Settings, get_settings

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from abc import ABC, abstractmethod
import asyncio
import random

# Стабильные User-Agent'ы
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
]


class BaseSniffer(ABC):
    def __init__(self, config: Settings | None = None):
        self.config = config or get_settings()
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    async def start(self):
        self.playwright = await async_playwright().start()

        self.browser = await self.playwright.chromium.launch(
            headless=self.config.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-gpu",
            ],
        )

        self.context = await self.browser.new_context(
            viewport={"width": self.config.viewport_width, "height": self.config.viewport_height},
            locale=self.config.locale,
            timezone_id=self.config.timezone_id,
            user_agent=random.choice(USER_AGENTS),
        )

        # Отключаем webdriver признак
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        self.page = await self.context.new_page()

    async def stop(self):
        await self.page.close()
        await self.context.close()
        await self.browser.close()
        await self.playwright.stop()

    @abstractmethod
    async def fetch_vacancies(self, query: str, **kwargs) -> list[dict]:
        pass

    async def _random_delay(self, min_sec: float | None = None, max_sec: float | None = None):
        min_sec = min_sec or self.config.delay_min
        max_sec = max_sec or self.config.delay_max
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)
