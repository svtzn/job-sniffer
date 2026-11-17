import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from app.config import get_settings
from app.db.migrations import upgrade_to_head_async
from app.db.session import dispose_engine
from app.telegram.handlers import router

logger = logging.getLogger(__name__)

COMMANDS = [
    BotCommand(command="search", description="Искать вакансии (или повторить последний поиск)"),
    BotCommand(command="filters", description="Фильтры поиска"),
    BotCommand(command="myfilters", description="Сохранённые фильтры"),
    BotCommand(command="help", description="Справка"),
]


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN не задан в .env")

    logger.info("Применяю миграции БД…")
    await upgrade_to_head_async()

    proxy_url = settings.telegram_proxy_url
    session = AiohttpSession(proxy=proxy_url) if proxy_url else None

    bot = Bot(
        token=settings.telegram_bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )
    dp = Dispatcher()
    dp.include_router(router)

    logger.info("Proxy: %s", proxy_url or "не задан — прямое подключение")
    await bot.set_my_commands(COMMANDS)
    logger.info("Job Sniffer запущен, жду сообщения…")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
