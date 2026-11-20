import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError
from aiogram.types import BotCommand

from app.config import get_settings
from app.db.migrations import upgrade_to_head_async
from app.db.session import dispose_engine
from app.telegram.handlers import router
from app.telegram.notifier import SubscriptionWorker
from app.telegram.session import build_session, describe_session, uses_custom_api

logger = logging.getLogger(__name__)

COMMANDS = [
    BotCommand(command="search", description="Искать вакансии (или повторить последний поиск)"),
    BotCommand(command="filters", description="Фильтры поиска"),
    BotCommand(command="myfilters", description="Сохранённые фильтры и подписки"),
    BotCommand(command="help", description="Справка"),
]


class StartupError(Exception):
    """Ошибка запуска, которую нужно показать пользователю без трейсбека."""


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging() -> None:
    # Ничего не делает, если логи уже настроены (например, своей запускалкой)
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


def _network_hint(bot: Bot, proxy_url: str) -> str:
    if proxy_url:
        return f"Проверь, что прокси {proxy_url} запущен."
    if uses_custom_api(bot.session.api):
        return "Проверь, что адрес TELEGRAM_API_BASE в .env открывается."
    return (
        "Если Telegram у тебя открывается только через VPN/прокси — "
        "укажи TELEGRAM_PROXY_URL или TELEGRAM_API_BASE в .env."
    )


async def _connect(bot: Bot, proxy_url: str) -> None:
    try:
        me = await bot.get_me()
        await bot.set_my_commands(COMMANDS)
    except TelegramUnauthorizedError as e:
        raise StartupError("Telegram отверг токен — проверь TELEGRAM_BOT_TOKEN в .env (выдаёт @BotFather).") from e
    except TelegramNetworkError as e:
        raise StartupError(f"Нет связи с Telegram ({e.message}). {_network_hint(bot, proxy_url)}") from e
    logger.info("Подключён как @%s", me.username)


async def main() -> None:
    setup_logging()
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise StartupError("TELEGRAM_BOT_TOKEN не задан в .env")

    logger.info("Применяю миграции БД…")
    await upgrade_to_head_async()

    proxy_url = settings.telegram_proxy_url
    bot = Bot(
        token=settings.telegram_bot_token,
        session=build_session(settings),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )
    worker = SubscriptionWorker(bot)
    dp = Dispatcher(worker=worker)  # worker доступен хендлерам как аргумент `worker`
    dp.include_router(router)

    worker_task: asyncio.Task | None = None
    try:
        logger.info("Telegram — %s", describe_session(bot.session, proxy_url))
        await _connect(bot, proxy_url)
        worker_task = asyncio.create_task(worker.run(), name="subscriptions")
        logger.info("Job Sniffer запущен, жду сообщения…")
        await dp.start_polling(bot)
    finally:
        if worker_task is not None:
            worker_task.cancel()
            with suppress(asyncio.CancelledError):
                await worker_task
        await worker.stop()
        await bot.session.close()
        await dispose_engine()


def run() -> None:
    """Точка входа `uv run job-sniffer`."""
    setup_logging()
    try:
        asyncio.run(main())
    except StartupError as e:
        logger.error("%s", e)
        raise SystemExit(1) from None
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
