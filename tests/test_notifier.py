from aiogram.methods import SendMessage

import app.config
from app.services import saved_filters, subscriptions
from app.services.filters import SearchFilters
from app.telegram.notifier import FAILURES_BEFORE_ALERT, SubscriptionWorker
from tests.conftest import CHAT_ID, make_vacancy


async def _filter_with_new(fake_search, count: int):
    info = await saved_filters.create(CHAT_ID, SearchFilters(text="python"), "Python")
    await subscriptions.set_subscribed(CHAT_ID, info.id, True)
    await subscriptions.check_filter(info.id)  # тихая проверка
    fake_search.vacancies = [make_vacancy(f"Vacancy {i}") for i in range(count)]
    return info


async def test_cycle_sends_cards_for_few_new(fake_search, telegram):
    bot, session = telegram
    await _filter_with_new(fake_search, 2)

    await SubscriptionWorker(bot, send_pause=0).run_cycle()

    sent = session.sent(SendMessage)
    assert len(sent) == 2
    assert "Новая вакансия" in sent[0].text and "Подходит: Python" in sent[0].text
    buttons = sent[0].reply_markup.inline_keyboard[0]
    assert buttons[0].url.startswith("https://hh.ru/vacancy/")
    assert buttons[1].callback_data.startswith("h:")
    assert await subscriptions.pending_for_chat(CHAT_ID) == []

    await SubscriptionWorker(bot, send_pause=0).run_cycle()  # повторно ничего не шлём
    assert len(session.sent(SendMessage)) == 2


async def test_many_new_become_one_digest(fake_search, telegram):
    bot, session = telegram
    await _filter_with_new(fake_search, 12)

    await SubscriptionWorker(bot, max_per_check=10, send_pause=0).run_cycle()

    (digest,) = session.sent(SendMessage)
    assert "Новых вакансий: 12" in digest.text
    assert digest.text.count("hh.ru/vacancy/") == 12
    assert await subscriptions.pending_for_chat(CHAT_ID) == []


async def test_quiet_hours_postpone_delivery(fake_search, telegram):
    bot, session = telegram
    await _filter_with_new(fake_search, 1)
    app.config.get_settings().quiet_hours = "00:00-23:59"

    await SubscriptionWorker(bot, send_pause=0).run_cycle()
    assert session.sent(SendMessage) == []
    assert len(await subscriptions.pending_for_chat(CHAT_ID)) == 1  # ждёт утра

    app.config.get_settings().quiet_hours = ""
    await SubscriptionWorker(bot, send_pause=0).run_cycle()
    assert len(session.sent(SendMessage)) == 1


async def test_failed_send_keeps_vacancy_pending(fake_search, telegram, monkeypatch):
    bot, session = telegram
    await _filter_with_new(fake_search, 1)
    worker = SubscriptionWorker(bot, send_pause=0)

    async def broken_send(*args, **kwargs):
        return False

    monkeypatch.setattr(worker, "_send", broken_send)
    await worker.run_cycle()
    assert len(await subscriptions.pending_for_chat(CHAT_ID)) == 1


async def test_alert_once_after_repeated_hh_failures(fake_search, telegram):
    bot, session = telegram
    info = await saved_filters.create(CHAT_ID, SearchFilters(text="python"), "Python")
    await subscriptions.set_subscribed(CHAT_ID, info.id, True)
    fake_search.error = TimeoutError("HH timeout")
    worker = SubscriptionWorker(bot, send_pause=0)

    for _ in range(FAILURES_BEFORE_ALERT + 2):
        await worker.run_cycle()

    alerts = [m for m in session.sent(SendMessage) if "HH не отвечает" in m.text]
    assert len(alerts) == 1

    fake_search.error = None
    await worker.run_cycle()
    assert worker._failures == {}
