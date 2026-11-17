"""Общие фикстуры: временная БД на каждый тест, фабрика вакансий, подменённый поиск, фейковый Telegram."""

import itertools
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.methods import EditMessageText, SendMessage, TelegramMethod
from aiogram.types import CallbackQuery, Chat, Message, Update, User

import app.config
from app.db import session as db_session
from app.db.migrations import upgrade_to_head_async
from app.services.search import LocationOutcome, SearchOutcome, merge_results
from app.sniffers.schemas import Salary, VacancyData


@pytest.fixture(autouse=True)
async def db(tmp_path, monkeypatch):
    """Чистая SQLite-база с применёнными миграциями и предсказуемые настройки."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}")
    app.config._settings = None
    await db_session.dispose_engine()

    settings = app.config.get_settings()
    # не зависеть от личного .env
    settings.quiet_hours = ""
    settings.subscription_interval_minutes = 15
    settings.subscription_max_per_check = 10
    settings.results_page_size = 5
    settings.home_area_id = 53

    await upgrade_to_head_async()
    yield
    await db_session.dispose_engine()
    app.config._settings = None


_ids = itertools.count(1000)


def make_vacancy(
    title: str = "Python developer",
    employer: str = "ООО Ромашка",
    vid: str | None = None,
    minutes_ago: int = 0,
    salary_from: int | None = 100_000,
) -> VacancyData:
    vid = vid or str(next(_ids))
    return VacancyData(
        id=vid,
        title=title,
        url=f"https://hh.ru/vacancy/{vid}",
        employer=employer,
        salary=Salary(amount_from=salary_from, currency="RUR", gross=False, mode="MONTH"),
        experience="between1And3",
        work_formats=["REMOTE"],
        area="Москва",
        published_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
    )


@pytest.fixture
def vacancy_factory() -> Callable[..., VacancyData]:
    return make_vacancy


class FakeSearch:
    """Подменяет search_vacancies: отдаёт заранее заданные вакансии, применяя «исключить слова»."""

    def __init__(self):
        self.vacancies: list[VacancyData] = []
        self.calls: list[dict] = []
        self.error: Exception | None = None

    async def __call__(self, filters, limit=None, newest_first=False):
        self.calls.append({"filters": filters, "limit": limit, "newest_first": newest_first})
        if self.error:
            raise self.error
        merged, matched = merge_results([list(self.vacancies)])
        kept = [v for v in merged if not filters.is_excluded(v.title)]
        return SearchOutcome(
            vacancies=kept,
            locations=[LocationOutcome(rule, len(self.vacancies), len(self.vacancies)) for rule in filters.locations],
            matched_locations={v.id: [0] for v in kept},
            excluded=len(merged) - len(kept),
        )


@pytest.fixture
def fake_search(monkeypatch) -> FakeSearch:
    fake = FakeSearch()
    import app.services.search as search_module
    import app.services.subscriptions as subscriptions_module

    monkeypatch.setattr(search_module, "search_vacancies", fake)
    monkeypatch.setattr(subscriptions_module, "search_vacancies", fake)
    return fake


# ---------------------------------------------------------------- фейковый Telegram

CHAT_ID = 777


class FakeTelegramSession(BaseSession):
    """Ничего не отправляет в сеть, записывает вызванные методы."""

    def __init__(self):
        super().__init__()
        self.calls: list[TelegramMethod] = []
        self._ids = itertools.count(100)

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if isinstance(method, SendMessage | EditMessageText):
            message_id = getattr(method, "message_id", None) or next(self._ids)
            chat = Chat(id=int(method.chat_id or CHAT_ID), type="private")
            return Message(message_id=message_id, date=datetime.now(), chat=chat, text=method.text).as_(bot)
        return True

    async def close(self):
        pass

    async def stream_content(self, *args, **kwargs):
        yield b""

    def sent(self, kind=SendMessage) -> list:
        return [c for c in self.calls if isinstance(c, kind)]

    def texts(self) -> list[str]:
        return [c.text for c in self.calls if isinstance(c, SendMessage | EditMessageText)]


class TelegramHarness:
    """Бот + диспетчер с настоящими хендлерами и фейковой сетью."""

    def __init__(self, dispatcher: Dispatcher, bot: Bot, session: FakeTelegramSession):
        self.dp, self.bot, self.session = dispatcher, bot, session
        self._update_ids = itertools.count(1)
        self._message_ids = itertools.count(10_000)
        self.user = User(id=CHAT_ID, is_bot=False, first_name="Tester")
        self.chat = Chat(id=CHAT_ID, type="private")

    async def send(self, text: str) -> None:
        message = Message(
            message_id=next(self._message_ids), date=datetime.now(), chat=self.chat, from_user=self.user, text=text
        )
        await self.dp.feed_update(self.bot, Update(update_id=next(self._update_ids), message=message))

    async def click(self, data: str, message_id: int = 1, message_text: str = "x", reply_markup=None) -> None:
        message = Message(
            message_id=message_id, date=datetime.now(), chat=self.chat, text=message_text, reply_markup=reply_markup
        )
        query = CallbackQuery(id="cb", from_user=self.user, chat_instance="ci", message=message, data=data)
        await self.dp.feed_update(self.bot, Update(update_id=next(self._update_ids), callback_query=query))


@pytest.fixture
def telegram():
    session = FakeTelegramSession()
    bot = Bot("123456:TEST", session=session, default=DefaultBotProperties(parse_mode="HTML"))
    return bot, session


@pytest.fixture
def harness(telegram, monkeypatch):
    """Диспетчер с роутером бота. Воркер подписок — настоящий, но фоновые задачи выполняются сразу."""
    from app.telegram import handlers, state
    from app.telegram.notifier import SubscriptionWorker

    monkeypatch.setattr(state, "_sessions", {})
    bot, session = telegram
    worker = SubscriptionWorker(bot, send_pause=0)
    pending: list = []
    monkeypatch.setattr(worker, "check_soon", lambda filter_id, chat_id: pending.append((filter_id, chat_id)))

    dp = Dispatcher(worker=worker)
    # роутер — модульный синглтон; aiogram не даёт подключить его к двум диспетчерам
    handlers.router._parent_router = None
    dp.include_router(handlers.router)
    h = TelegramHarness(dp, bot, session)
    h.worker = worker
    h.pending_checks = pending
    yield h
    handlers.router._parent_router = None
