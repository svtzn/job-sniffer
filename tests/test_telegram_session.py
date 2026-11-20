"""Сессия Telegram: настройки по умолчанию, свой адрес API, режим соединений, устойчивость к сбоям."""

import asyncio

import pytest
from aiogram import Bot
from aiogram.client.telegram import PRODUCTION, TelegramAPIServer
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage

from app.config import Settings
from app.services import search as search_module
from app.services.filters import SearchFilters
from app.sniffers import base as base_module
from app.sniffers.schemas import SearchResult
from app.telegram import session as session_module
from app.telegram.session import TolerantRequests, build_session, describe_session
from tests.conftest import CHAT_ID, FakeTelegramSession

WORKER = "https://example.workers.dev"


def _settings(**env) -> Settings:
    return Settings(_env_file=None, telegram_bot_token="1:x", **env)


def test_defaults_match_plain_aiogram(monkeypatch):
    for key in ("TELEGRAM_API_BASE", "TELEGRAM_KEEPALIVE", "TELEGRAM_PROXY_URL", "TELEGRAM_TIMEOUT"):
        monkeypatch.delenv(key, raising=False)
    session = build_session(Settings(_env_file=None))

    assert session.api is PRODUCTION
    assert "force_close" not in session._connector_init
    assert session.timeout == 15
    assert describe_session(session, "") == "API: api.telegram.org, прокси: нет, таймаут: 15 с"


def test_empty_values_in_env_mean_defaults(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_BASE", "")
    monkeypatch.setenv("TELEGRAM_KEEPALIVE", "")
    session = build_session(Settings(_env_file=None))
    assert session.api is PRODUCTION and "force_close" not in session._connector_init


def test_custom_api_base_turns_off_keepalive():
    session = build_session(_settings(telegram_api_base=WORKER + "/"))

    assert session.api.api_url("TOKEN", "getMe") == f"{WORKER}/botTOKEN/getMe"
    assert session._connector_init["force_close"] is True
    assert "новое соединение на каждый запрос" in describe_session(session, "")
    assert "TOKEN" not in describe_session(session, "")


def test_keepalive_can_be_forced_either_way():
    assert (
        "force_close" not in build_session(_settings(telegram_api_base=WORKER, telegram_keepalive=True))._connector_init
    )
    assert build_session(_settings(telegram_keepalive=False))._connector_init["force_close"] is True


def test_patched_production_like_old_run_bot_is_detected(monkeypatch):
    # старый run_bot.py подменяет адрес прямо в aiogram — режим соединений всё равно должен включиться
    monkeypatch.setattr(session_module, "PRODUCTION", TelegramAPIServer.from_base(WORKER))
    session = build_session(_settings())
    assert session._connector_init["force_close"] is True


def test_proxy_keeps_working_with_fresh_connections():
    session = build_session(_settings(telegram_proxy_url="socks5://127.0.0.1:1080", telegram_keepalive=False))
    assert session._connector_init["force_close"] is True
    assert "socks5://127.0.0.1:1080" in describe_session(session, "socks5://127.0.0.1:1080")


# ---------------------------------------------------------------- устойчивость к сбоям


class FlakySession(FakeTelegramSession):
    """Первые запросы нужного типа падают заданными ошибками."""

    def __init__(self, failures: dict[type, list[Exception]]):
        super().__init__()
        self.failures = failures
        self.middleware(TolerantRequests())

    async def make_request(self, bot, method, timeout=None):
        pending = self.failures.get(type(method))
        if pending:
            self.calls.append(method)
            raise pending.pop(0)
        return await super().make_request(bot, method, timeout)


def _bot(session) -> Bot:
    return Bot("123456:TEST", session=session)


def _bad_request(method, text):
    return TelegramBadRequest(method=method, message=f"Bad Request: {text}")


async def test_stale_callback_answer_is_not_an_error():
    method = AnswerCallbackQuery(callback_query_id="cb")
    session = FlakySession(
        {AnswerCallbackQuery: [_bad_request(method, "query is too old and response timeout expired")]}
    )
    assert await _bot(session)(method) is True


async def test_network_error_on_callback_answer_is_not_an_error():
    method = AnswerCallbackQuery(callback_query_id="cb")
    session = FlakySession(
        {AnswerCallbackQuery: [TelegramNetworkError(method=method, message="Request timeout error")]}
    )
    assert await _bot(session)(method) is True


async def test_other_bad_requests_still_raise():
    method = AnswerCallbackQuery(callback_query_id="cb")
    session = FlakySession({AnswerCallbackQuery: [_bad_request(method, "something else")]})
    with pytest.raises(TelegramBadRequest):
        await _bot(session)(method)


async def test_edit_is_retried_once_after_network_error():
    method = EditMessageText(chat_id=CHAT_ID, message_id=5, text="hi")
    session = FlakySession({EditMessageText: [TelegramNetworkError(method=method, message="Request timeout error")]})
    await _bot(session)(method)
    assert len(session.sent(EditMessageText)) == 2


async def test_send_is_not_retried():
    method = SendMessage(chat_id=CHAT_ID, text="hi")
    session = FlakySession({SendMessage: [TelegramNetworkError(method=method, message="Request timeout error")]})
    with pytest.raises(TelegramNetworkError):
        await _bot(session)(method)
    assert len(session.sent()) == 1


async def test_button_press_is_answered_before_redrawing(harness):
    await harness.click("f:salary:")
    kinds = [type(c) for c in harness.session.calls]
    assert kinds.index(AnswerCallbackQuery) < kinds.index(EditMessageText)


# ---------------------------------------------------------------- ограничения времени поиска


class HangingSniffer:
    def __init__(self, settings):
        self.stopped = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        self.stopped = True

    async def fetch_vacancies(self, query, limit):
        await asyncio.sleep(60)
        return SearchResult(vacancies=[], total_found=0)


async def test_hanging_search_is_cut_and_frees_the_queue(monkeypatch):
    monkeypatch.setattr(search_module, "HHSniffer", HangingSniffer)
    monkeypatch.setattr(search_module.get_settings(), "search_timeout_seconds", 1)

    with pytest.raises(search_module.SearchTimeoutError):
        await search_module.search_vacancies(SearchFilters(text="python"))
    assert not search_module.search_is_busy()


class _HangingResource:
    async def close(self):
        await asyncio.sleep(60)


class _HangingPlaywright:
    async def stop(self):
        await asyncio.sleep(60)


async def test_browser_stop_never_hangs(monkeypatch):
    monkeypatch.setattr(base_module, "CLOSE_TIMEOUT_SECONDS", 0.05)
    sniffer = search_module.HHSniffer(_settings())
    sniffer.page = sniffer.context = sniffer.browser = _HangingResource()
    sniffer.playwright = _HangingPlaywright()

    await asyncio.wait_for(sniffer.stop(), 2)
    assert sniffer.browser is None and sniffer.playwright is None
