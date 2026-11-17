"""Фоновый воркер подписок: раз в N минут проверяет подписки и шлёт новые вакансии.

Логика «что новое» — в app.services.subscriptions; здесь только расписание,
отправка в Telegram и обработка сбоев.
"""

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from app.config import get_settings
from app.services import saved_filters, subscriptions
from app.telegram.formatter import format_digest, format_hh_unavailable, format_notification
from app.telegram.keyboards import notification_keyboard

logger = logging.getLogger(__name__)

FAILURES_BEFORE_ALERT = 3
SEND_PAUSE_SECONDS = 1.0  # между сообщениями в один чат (лимиты Telegram)


class SubscriptionWorker:
    def __init__(
        self,
        bot: Bot,
        interval_minutes: int | None = None,
        max_per_check: int | None = None,
        send_pause: float = SEND_PAUSE_SECONDS,
    ):
        settings = get_settings()
        self.bot = bot
        self.interval = max(1, interval_minutes or settings.subscription_interval_minutes) * 60
        self.max_per_check = max(1, max_per_check or settings.subscription_max_per_check)
        self.send_pause = send_pause
        self._failures: dict[int, int] = {}  # filter_id -> неудач подряд
        self._background: set[asyncio.Task] = set()

    # ---------------------------------------------------------------- цикл

    async def run(self) -> None:
        logger.info("Подписки: проверка каждые %s мин", self.interval // 60)
        while True:
            try:
                await self.run_cycle()
            except Exception:
                logger.exception("Подписки: сбой цикла проверки")
            await asyncio.sleep(self.interval)

    async def run_cycle(self) -> None:
        for filter_id, chat_id in await subscriptions.subscribed_filters():
            await self._check(filter_id, chat_id)

        if subscriptions.is_quiet_now():
            logger.info("Подписки: тихие часы, отправку откладываю")
            return
        for chat_id in await subscriptions.chats_with_pending():
            await self.deliver(chat_id)

    def check_soon(self, filter_id: int, chat_id: int) -> None:
        """Первая («тихая») проверка сразу после включения подписки, не блокируя хендлер."""
        task = asyncio.create_task(self._check(filter_id, chat_id))
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    async def _check(self, filter_id: int, chat_id: int) -> None:
        try:
            await subscriptions.check_filter(filter_id)
        except Exception as e:
            count = self._failures.get(filter_id, 0) + 1
            self._failures[filter_id] = count
            logger.warning("Подписка %s: ошибка проверки (%s подряд): %s", filter_id, count, e)
            if count == FAILURES_BEFORE_ALERT:
                await self._alert_unavailable(filter_id, chat_id)
        else:
            self._failures.pop(filter_id, None)

    async def _alert_unavailable(self, filter_id: int, chat_id: int) -> None:
        info = await saved_filters.get(chat_id, filter_id)
        if info is not None:
            await self._send(chat_id, format_hh_unavailable(info.name))

    # ---------------------------------------------------------------- отправка

    async def deliver(self, chat_id: int) -> int:
        """Отправляет очередь чата. Возвращает число отправленных вакансий."""
        items = await subscriptions.pending_for_chat(chat_id)
        if not items:
            return 0

        if len(items) > self.max_per_check:
            text = format_digest([(item.vacancy, item.filter_names) for item in items])
            if await self._send(chat_id, text):
                await subscriptions.mark_notified(chat_id, [item.db_id for item in items])
                return len(items)
            return 0

        sent = 0
        for item in items:
            ok = await self._send(
                chat_id,
                format_notification(item.vacancy, item.filter_names),
                reply_markup=notification_keyboard(item.vacancy.url, item.db_id),
            )
            if not ok:
                break  # остальное останется pending и уйдёт в следующий раз
            await subscriptions.mark_notified(chat_id, [item.db_id])
            sent += 1
            await asyncio.sleep(self.send_pause)
        return sent

    async def _send(self, chat_id: int, text: str, reply_markup=None) -> bool:
        for _ in range(2):
            try:
                await self.bot.send_message(chat_id, text, reply_markup=reply_markup)
                return True
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after)
            except TelegramForbiddenError:
                logger.warning("Чат %s заблокировал бота — уведомления не доставить", chat_id)
                return False
            except Exception:
                logger.exception("Не удалось отправить уведомление в чат %s", chat_id)
                return False
        return False

    async def stop(self) -> None:
        for task in list(self._background):
            task.cancel()
