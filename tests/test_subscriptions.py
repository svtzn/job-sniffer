from datetime import datetime

from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import FilterVacancy
from app.services import saved_filters, subscriptions
from app.services.filters import SearchFilters
from app.services.search import search_and_store
from tests.conftest import CHAT_ID, make_vacancy


async def _subscribed_filter(text="python", name="Python", chat_id=CHAT_ID):
    info = await saved_filters.create(chat_id, SearchFilters(text=text), name)
    assert await subscriptions.set_subscribed(chat_id, info.id, True) is True
    return info


async def _statuses(filter_id: int) -> dict[int, str]:
    async with get_sessionmaker()() as session:
        rows = await session.scalars(select(FilterVacancy).where(FilterVacancy.filter_id == filter_id))
        return {r.vacancy_id: r.status for r in rows}


async def test_first_check_is_silent_then_only_new_are_pending(fake_search):
    info = await _subscribed_filter()
    fake_search.vacancies = [make_vacancy("Old 1"), make_vacancy("Old 2")]

    first = await subscriptions.check_filter(info.id)
    assert first.baseline and first.new == 0
    assert await subscriptions.pending_for_chat(CHAT_ID) == []
    assert fake_search.calls[-1]["newest_first"] is True

    fake_search.vacancies = [make_vacancy("Fresh"), *fake_search.vacancies]
    second = await subscriptions.check_filter(info.id)

    assert not second.baseline and second.new == 1
    pending = await subscriptions.pending_for_chat(CHAT_ID)
    assert [p.vacancy.title for p in pending] == ["Fresh"]
    assert pending[0].filter_names == ["Python"]


async def test_vacancy_matching_two_filters_is_one_notification(fake_search):
    a = await _subscribed_filter("python", "Python удалёнка")
    b = await _subscribed_filter("backend", "Backend КРД")
    for f in (a, b):
        await subscriptions.check_filter(f.id)  # тихие проверки

    shared = make_vacancy("Python backend")
    fake_search.vacancies = [shared]
    for f in (a, b):
        await subscriptions.check_filter(f.id)

    pending = await subscriptions.pending_for_chat(CHAT_ID)
    assert len(pending) == 1
    assert pending[0].filter_names == ["Python удалёнка", "Backend КРД"]

    await subscriptions.mark_notified(CHAT_ID, [pending[0].db_id])
    assert await subscriptions.pending_for_chat(CHAT_ID) == []
    assert set((await _statuses(a.id)).values()) == {"notified"}


async def test_vacancy_seen_in_manual_search_is_not_notified(fake_search):
    info = await _subscribed_filter()
    await subscriptions.check_filter(info.id)

    seen_manually = make_vacancy("Seen manually")
    fake_search.vacancies = [seen_manually]
    await search_and_store(SearchFilters(text="python"), saved_filter_id=info.id)

    await subscriptions.check_filter(info.id)
    assert await subscriptions.pending_for_chat(CHAT_ID) == []


async def test_hide_marks_vacancy_hidden_in_all_chat_filters(fake_search):
    info = await _subscribed_filter()
    await subscriptions.check_filter(info.id)
    fake_search.vacancies = [make_vacancy("Annoying")]
    await subscriptions.check_filter(info.id)
    (item,) = await subscriptions.pending_for_chat(CHAT_ID)

    assert await subscriptions.hide_vacancy(CHAT_ID, item.db_id)
    assert await subscriptions.hide_vacancy(CHAT_ID + 1, item.db_id) is False  # чужой чат не может
    assert await _statuses(info.id) == {item.db_id: "hidden"}
    assert await subscriptions.pending_for_chat(CHAT_ID) == []


async def test_unsubscribe_drops_queue_and_resubscribe_is_silent_again(fake_search):
    info = await _subscribed_filter()
    await subscriptions.check_filter(info.id)
    fake_search.vacancies = [make_vacancy("Waiting")]
    await subscriptions.check_filter(info.id)
    assert len(await subscriptions.pending_for_chat(CHAT_ID)) == 1

    await subscriptions.set_subscribed(CHAT_ID, info.id, False)
    assert await subscriptions.pending_for_chat(CHAT_ID) == []
    assert await subscriptions.check_filter(info.id) is None  # выключенный не проверяется

    await subscriptions.set_subscribed(CHAT_ID, info.id, True)
    fake_search.vacancies.append(make_vacancy("Arrived while off"))
    again = await subscriptions.check_filter(info.id)
    assert again.baseline and await subscriptions.pending_for_chat(CHAT_ID) == []


async def test_changing_saved_filter_restarts_baseline(fake_search):
    info = await _subscribed_filter()
    await subscriptions.check_filter(info.id)

    changed = info.filters.copy()
    changed.text = "golang"
    await saved_filters.update_filters(CHAT_ID, info.id, changed)

    fake_search.vacancies = [make_vacancy(f"Go {i}") for i in range(5)]
    result = await subscriptions.check_filter(info.id)
    assert result.baseline and await subscriptions.pending_for_chat(CHAT_ID) == []


async def test_exclude_words_apply_to_subscriptions(fake_search):
    info = await saved_filters.create(CHAT_ID, SearchFilters(text="python", exclude_words=["senior"]), "Py")
    await subscriptions.set_subscribed(CHAT_ID, info.id, True)
    await subscriptions.check_filter(info.id)

    fake_search.vacancies = [make_vacancy("Senior Python"), make_vacancy("Junior Python")]
    await subscriptions.check_filter(info.id)

    assert [p.vacancy.title for p in await subscriptions.pending_for_chat(CHAT_ID)] == ["Junior Python"]


async def test_other_chat_cannot_toggle_subscription():
    info = await saved_filters.create(CHAT_ID, SearchFilters(text="python"), "Py")
    assert await subscriptions.set_subscribed(CHAT_ID + 1, info.id, True) is None


def test_quiet_hours():
    assert subscriptions.parse_quiet_hours("") is None
    assert subscriptions.parse_quiet_hours("bad") is None
    assert subscriptions.is_quiet_now(datetime(2026, 1, 1, 2, 0), "23-8")
    assert subscriptions.is_quiet_now(datetime(2026, 1, 1, 23, 30), "23-8")
    assert not subscriptions.is_quiet_now(datetime(2026, 1, 1, 12, 0), "23-8")
    assert subscriptions.is_quiet_now(datetime(2026, 1, 1, 13, 0), "12:30-14")
    assert not subscriptions.is_quiet_now(datetime(2026, 1, 1, 14, 0), "12:30-14")
