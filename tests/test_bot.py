"""Сценарии через настоящие хендлеры aiogram с фейковой сетью Telegram."""

from aiogram.methods import AnswerCallbackQuery, EditMessageReplyMarkup, EditMessageText, SendMessage

from app.services import saved_filters, subscriptions
from app.services.filters import SearchFilters
from app.telegram.keyboards import notification_keyboard
from app.telegram.state import get_session
from tests.conftest import CHAT_ID, make_vacancy


def _alerts(session) -> list[str]:
    return [c.text for c in session.calls if isinstance(c, AnswerCallbackQuery) and c.text]


async def test_search_shows_results_and_excluded_count(harness, fake_search):
    fake_search.vacancies = [make_vacancy("Senior Python"), make_vacancy("Junior Python")]
    get_session(CHAT_ID).filters.set_exclude_words("senior")

    await harness.send("python")

    result = [c for c in harness.session.calls if isinstance(c, EditMessageText)][-1].text
    assert "Junior Python" in result and "Senior Python" not in result
    assert "Скрыто по исключённым словам: 1" in result


async def test_exclude_words_dialog(harness):
    await harness.click("f:exclude:")
    assert "Исключить слова" in harness.session.texts()[-1]

    await harness.send("senior, Lead")
    assert get_session(CHAT_ID).filters.exclude_words == ["senior", "lead"]
    assert "без: senior, lead" in harness.session.texts()[-1]  # панель фильтров

    await harness.click("f:exclude:")
    await harness.send("-")
    assert get_session(CHAT_ID).filters.exclude_words == []


async def test_exclude_dialog_cancel_returns_to_search(harness, fake_search):
    await harness.click("f:exclude:")
    await harness.click("a:cancel_input")
    fake_search.vacancies = [make_vacancy()]

    await harness.send("python")  # это уже поисковый запрос, а не слова

    assert get_session(CHAT_ID).filters.exclude_words == []
    assert fake_search.calls


async def test_subscription_toggle_from_list(harness, fake_search):
    info = await saved_filters.create(CHAT_ID, SearchFilters(text="python"), "Python")

    await harness.click(f"s:sub:{info.id}", message_text="📂 Мои фильтры")

    assert (await saved_filters.get(CHAT_ID, info.id)).is_subscribed
    assert harness.pending_checks == [(info.id, CHAT_ID)]  # первая тихая проверка запущена
    assert any("Подписка на <b>Python</b> включена" in t for t in harness.session.texts())
    listing = [c for c in harness.session.calls if isinstance(c, EditMessageText)][-1]
    assert "🔔" in listing.text
    assert any(b.callback_data == f"s:unsub:{info.id}" for row in listing.reply_markup.inline_keyboard for b in row)

    await harness.click(f"s:unsub:{info.id}", message_text="📂 Мои фильтры")
    assert not (await saved_filters.get(CHAT_ID, info.id)).is_subscribed


async def test_cannot_subscribe_to_foreign_or_deleted_filter(harness):
    other = await saved_filters.create(CHAT_ID + 5, SearchFilters(text="go"), "Чужой")

    await harness.click(f"s:sub:{other.id}")

    assert "Этот фильтр уже удалён" in _alerts(harness.session)
    assert not (await saved_filters.get(CHAT_ID + 5, other.id)).is_subscribed


async def test_hide_button_on_notification(harness, fake_search):
    info = await saved_filters.create(CHAT_ID, SearchFilters(text="python"), "Python")
    await subscriptions.set_subscribed(CHAT_ID, info.id, True)
    await subscriptions.check_filter(info.id)
    fake_search.vacancies = [make_vacancy("Meh")]
    await subscriptions.check_filter(info.id)
    (item,) = await subscriptions.pending_for_chat(CHAT_ID)
    markup = notification_keyboard(item.vacancy.url, item.db_id)

    await harness.click(f"h:{item.db_id}", reply_markup=markup)

    assert await subscriptions.pending_for_chat(CHAT_ID) == []
    edit = [c for c in harness.session.calls if isinstance(c, EditMessageReplyMarkup)][-1]
    (row,) = edit.reply_markup.inline_keyboard
    assert len(row) == 1 and row[0].url == item.vacancy.url


async def test_saved_filter_save_and_run_marks_seen(harness, fake_search):
    fake_search.vacancies = [make_vacancy("One"), make_vacancy("Two")]
    await harness.send("python")
    await harness.click("s:save:0")
    (info,) = await saved_filters.list_for_chat(CHAT_ID)

    await harness.click(f"s:run:{info.id}")
    await subscriptions.set_subscribed(CHAT_ID, info.id, True)
    await subscriptions.check_filter(info.id)  # тихая
    await subscriptions.check_filter(info.id)

    # вакансии из ручного запуска по сохранённому фильтру не придут уведомлением
    assert await subscriptions.pending_for_chat(CHAT_ID) == []
    assert any(isinstance(c, SendMessage) and "Сохранено как" in c.text for c in harness.session.calls)
