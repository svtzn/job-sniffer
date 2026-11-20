"""HTTP-сессия бота: свой адрес Bot API, прокси, таймауты, режим соединений.

По умолчанию (без настроек) — обычная сессия aiogram до api.telegram.org.
"""

import logging

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.session.middlewares.base import BaseRequestMiddleware, NextRequestMiddlewareType
from aiogram.client.telegram import PRODUCTION, TelegramAPIServer
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.methods import AnswerCallbackQuery, EditMessageReplyMarkup, EditMessageText, TelegramMethod
from aiogram.methods.base import TelegramType

from app.config import Settings

logger = logging.getLogger(__name__)

OFFICIAL_API_PREFIX = "https://api.telegram.org/"
_STALE_QUERY_MARKERS = ("query is too old", "query id is invalid")


def uses_custom_api(api: TelegramAPIServer) -> bool:
    # Сравниваем итоговый адрес, а не настройку: так видна и подмена PRODUCTION снаружи (старый run_bot.py)
    return not api.base.startswith(OFFICIAL_API_PREFIX)


def build_session(settings: Settings) -> AiohttpSession:
    api = TelegramAPIServer.from_base(settings.telegram_api_base) if settings.telegram_api_base else PRODUCTION
    session = AiohttpSession(proxy=settings.telegram_proxy_url or None, api=api, timeout=settings.telegram_timeout)

    keepalive = settings.telegram_keepalive
    if keepalive is None:
        keepalive = not uses_custom_api(api)
    if not keepalive:
        # Новое соединение на каждый запрос: «замороженное» провайдером соединение не переиспользуется
        session._connector_init["force_close"] = True
    session.keepalive = keepalive

    session.middleware(TolerantRequests())
    return session


def describe_session(session: AiohttpSession, proxy_url: str) -> str:
    api = session.api.base.split("/bot", 1)[0] if uses_custom_api(session.api) else "api.telegram.org"
    parts = [f"API: {api}", f"прокси: {proxy_url or 'нет'}", f"таймаут: {session.timeout:g} с"]
    if not getattr(session, "keepalive", True):
        parts.append("новое соединение на каждый запрос")
    return ", ".join(parts)


def is_stale_query(error: TelegramBadRequest) -> bool:
    message = error.message.lower()
    return any(marker in message for marker in _STALE_QUERY_MARKERS)


class TolerantRequests(BaseRequestMiddleware):
    """Сбои, из-за которых не стоит ронять обработчик.

    - Подтверждение нажатия кнопки — косметика: если оно опоздало или не дошло, это строка в логе.
    - Редактирование при сетевом сбое повторяется один раз (повтор безопасен: в худшем случае
      «message is not modified»). Отправку сообщений не повторяем — она могла дойти, был бы дубль.
    """

    async def __call__(
        self,
        make_request: NextRequestMiddlewareType[TelegramType],
        bot: Bot,
        method: TelegramMethod[TelegramType],
    ):
        if isinstance(method, AnswerCallbackQuery):
            try:
                return await make_request(bot, method)
            except TelegramBadRequest as e:
                if not is_stale_query(e):
                    raise
                logger.warning("Нажатие кнопки подтверждено слишком поздно (Telegram: %s)", e.message)
            except TelegramNetworkError as e:
                logger.warning("Не удалось подтвердить нажатие кнопки: %s", e.message)
            return True

        if isinstance(method, EditMessageText | EditMessageReplyMarkup):
            try:
                return await make_request(bot, method)
            except TelegramNetworkError as e:
                logger.warning("Сбой сети при редактировании сообщения, повторяю: %s", e.message)
                return await make_request(bot, method)

        return await make_request(bot, method)
