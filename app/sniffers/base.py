import asyncio
import logging
import random
from abc import ABC, abstractmethod
from contextlib import suppress

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from app.config import Settings, get_settings
from app.sniffers.schemas import SearchResult

logger = logging.getLogger(__name__)

CLOSE_TIMEOUT_SECONDS = 15

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
        self.playwright = None

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
        # Безопасно вызывать даже если start() упал на полпути.
        # Каждый шаг ограничен по времени: зависший Chromium не должен держать бота.
        for resource in (self.page, self.context, self.browser):
            if resource is not None:
                with suppress(Exception):
                    await asyncio.wait_for(resource.close(), CLOSE_TIMEOUT_SECONDS)
        if getattr(self, "playwright", None) is not None:
            try:
                # Остановка драйвера Playwright завершает и процесс браузера
                await asyncio.wait_for(self.playwright.stop(), CLOSE_TIMEOUT_SECONDS)
            except Exception as e:
                logger.warning("Браузер не закрылся за %s с: %r", CLOSE_TIMEOUT_SECONDS, e)
        self.page = self.context = self.browser = None
        self.playwright = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *exc):
        await self.stop()

    @abstractmethod
    async def fetch_vacancies(self, query, **kwargs) -> SearchResult:
        pass

    async def _random_delay(self, min_sec: float | None = None, max_sec: float | None = None):
        min_sec = min_sec or self.config.delay_min
        max_sec = max_sec or self.config.delay_max
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)
