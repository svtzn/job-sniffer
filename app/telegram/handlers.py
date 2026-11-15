"""Telegram-хендлеры. Здесь только UI: разбор нажатий, состояние чата, отправка сообщений.
Поиск и работа с HH — в app.services.search.

Сценарий:
  /start или /filters  -> панель фильтров (inline-кнопки)
                          локации: «регион + формат», выдача — их объединение
  любой текст          -> поиск по этому тексту с текущими фильтрами
  /search [текст]      -> то же самое; без текста — повтор последнего запроса
  выдача               -> ◀️ 2/20 ▶️, 🔄 Обновить, ⚙️ Фильтры
"""

import logging
from contextlib import suppress

from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart

from app.config import get_settings
from app.services.filters import MAX_LOCATIONS, LocationRule, SearchFilters
from app.services.search import search_is_busy, search_vacancies
from app.sniffers.hh.query import EmploymentForm, Experience, WorkFormat
from app.telegram.formatter import (
    format_error,
    format_filters_panel,
    format_location_editor,
    format_results_page,
)
from app.telegram.keyboards import (
    ActionCb,
    FilterCb,
    LocCb,
    PageCb,
    decode_area,
    filters_keyboard,
    location_editor_keyboard,
    results_keyboard,
)
from app.telegram.state import ChatSession, get_session

logger = logging.getLogger(__name__)
router = Router()

HELP_TEXT = (
    "🐽 <b>Job Sniffer</b> — поиск вакансий на HH.ru\n\n"
    "1. Настрой фильтры кнопками (/filters). Можно задать несколько локаций — "
    "например, удалёнка по России + офис в своём городе, выдача будет общей\n"
    "2. Отправь текст запроса, например <code>python backend</code>\n"
    "3. Листай выдачу кнопками ◀️ ▶️\n\n"
    "<b>Команды</b>\n"
    "/filters — фильтры поиска\n"
    "/search <i>текст</i> — искать (без текста — повторить последний запрос)\n"
    "/help — эта справка"
)


def _session(chat_id: int) -> ChatSession:
    return get_session(chat_id, page_size=get_settings().results_page_size)


def _home_area_id() -> int:
    return get_settings().home_area_id


async def _safe_edit(message: types.Message, text: str, reply_markup=None) -> None:
    """edit_text, который не падает на «message is not modified»."""
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


def _render_results(session: ChatSession) -> tuple[str, types.InlineKeyboardMarkup]:
    text = format_results_page(
        session.result,
        session.result_filters,
        session.page_vacancies(),
        session.page,
        session.pages,
        session.page_size,
    )
    return text, results_keyboard(session.page, session.pages)


async def _run_search(message: types.Message, session: ChatSession, filters: SearchFilters) -> None:
    """message — сообщение, в чат которого отправляем статус и выдачу."""
    if session.searching:
        await message.answer("⏳ Ещё ищу по прошлому запросу, подожди немного.")
        return

    session.searching = True
    queue_note = "\n(другой поиск уже идёт — ты следующий в очереди)" if search_is_busy() else ""
    where = f" по {len(filters.locations)} локациям" if len(filters.locations) > 1 else ""
    status = await message.answer(
        f"⏳ Ищу «{filters.text}» на HH{where}… обычно это 10–40 секунд.{queue_note}",
        parse_mode=None,
    )
    try:
        result = await search_vacancies(filters)
    except Exception as e:
        logger.exception("Ошибка поиска для chat=%s", message.chat.id)
        await _safe_edit(status, format_error(e))
        return
    finally:
        session.searching = False

    session.set_result(result, filters, status.message_id)
    text, keyboard = _render_results(session)
    await _safe_edit(status, text, reply_markup=keyboard)


async def _send_filters_panel(message: types.Message, session: ChatSession) -> None:
    await message.answer(
        format_filters_panel(session.filters),
        reply_markup=filters_keyboard(session.filters, _home_area_id()),
    )


async def _show_filters_panel(message: types.Message, session: ChatSession) -> None:
    """Перерисовать панель фильтров в том же сообщении."""
    await _safe_edit(
        message,
        format_filters_panel(session.filters),
        reply_markup=filters_keyboard(session.filters, _home_area_id()),
    )


async def _show_location_editor(message: types.Message, session: ChatSession, index: int) -> None:
    await _safe_edit(
        message,
        format_location_editor(session.filters, index),
        reply_markup=location_editor_keyboard(session.filters, index, _home_area_id()),
    )


# ---------------------------------------------------------------- commands

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    session = _session(message.chat.id)
    await message.answer(HELP_TEXT)
    await _send_filters_panel(message, session)


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(HELP_TEXT)


@router.message(Command("filters"))
async def cmd_filters(message: types.Message):
    await _send_filters_panel(message, _session(message.chat.id))


@router.message(Command("search"))
async def cmd_search(message: types.Message, command: CommandObject):
    session = _session(message.chat.id)
    if command.args:
        session.filters.text = command.args.strip()
    if not session.filters.text:
        await message.answer("Напиши, что искать: <code>/search python</code> или просто текст запроса.")
        return
    await _run_search(message, session, session.filters.copy())


@router.message(F.text & ~F.text.startswith("/"))
async def handle_query_text(message: types.Message):
    session = _session(message.chat.id)
    session.filters.text = message.text.strip()
    await _run_search(message, session, session.filters.copy())


@router.message(F.text.startswith("/"))
async def handle_unknown_command(message: types.Message):
    await message.answer("Не знаю такую команду. /help — список команд.")


# ---------------------------------------------------------------- filters (общая часть)

_ENUMS = {"emp": EmploymentForm, "exp": Experience}
_SETS = {"emp": "employment_forms", "exp": "experiences"}


@router.callback_query(FilterCb.filter())
async def on_filter(callback: types.CallbackQuery, callback_data: FilterCb):
    session = _session(callback.message.chat.id)
    filters = session.filters

    if callback_data.group in _ENUMS:
        try:
            value = _ENUMS[callback_data.group](callback_data.value)
        except ValueError:
            await callback.answer()
            return
        selected: set = getattr(filters, _SETS[callback_data.group])
        selected.symmetric_difference_update({value})
    elif callback_data.group == "salary":
        filters.only_with_salary = not filters.only_with_salary

    await _show_filters_panel(callback.message, session)
    await callback.answer()


# ---------------------------------------------------------------- локации

@router.callback_query(LocCb.filter())
async def on_location(callback: types.CallbackQuery, callback_data: LocCb):
    session = _session(callback.message.chat.id)
    filters = session.filters
    action, idx = callback_data.action, callback_data.idx

    if action == "add":
        new_idx = filters.add_location(LocationRule(area_id=_home_area_id()))
        if new_idx is None:
            await callback.answer(f"Больше {MAX_LOCATIONS} локаций не поддерживается", show_alert=True)
            return
        await _show_location_editor(callback.message, session, new_idx)
        await callback.answer()
        return

    if action == "preset":
        filters.apply_remote_plus_home(_home_area_id())
        await _show_filters_panel(callback.message, session)
        await callback.answer("Готово: удалёнка по России + офис/гибрид в твоём городе")
        return

    if action == "done":
        await _show_filters_panel(callback.message, session)
        await callback.answer()
        return

    # дальше — действия над конкретной локацией; индекс мог устареть
    if not 0 <= idx < len(filters.locations):
        await _show_filters_panel(callback.message, session)
        await callback.answer("Эта локация уже удалена")
        return
    rule = filters.locations[idx]

    if action == "del":
        filters.remove_location(idx)
        await _show_filters_panel(callback.message, session)
        await callback.answer("Локация удалена")
        return

    if action == "area":
        with suppress(ValueError):
            rule.area_id = decode_area(callback_data.value)
    elif action == "wf":
        with suppress(ValueError):
            rule.work_formats.symmetric_difference_update({WorkFormat(callback_data.value)})

    await _show_location_editor(callback.message, session, idx)
    await callback.answer()


# ---------------------------------------------------------------- actions

@router.callback_query(ActionCb.filter(F.action == "noop"))
async def on_noop(callback: types.CallbackQuery):
    await callback.answer()


@router.callback_query(ActionCb.filter(F.action == "search"))
async def on_search(callback: types.CallbackQuery):
    session = _session(callback.message.chat.id)
    if not session.filters.text:
        await callback.answer("Сначала отправь текст запроса, например «python»", show_alert=True)
        return
    await callback.answer()
    await _run_search(callback.message, session, session.filters.copy())


@router.callback_query(ActionCb.filter(F.action == "reset"))
async def on_reset(callback: types.CallbackQuery):
    session = _session(callback.message.chat.id)
    session.filters = SearchFilters()
    await _show_filters_panel(callback.message, session)
    await callback.answer("Фильтры сброшены")


@router.callback_query(ActionCb.filter(F.action == "filters"))
async def on_show_filters(callback: types.CallbackQuery):
    await callback.answer()
    await _send_filters_panel(callback.message, _session(callback.message.chat.id))


@router.callback_query(ActionCb.filter(F.action == "refresh"))
async def on_refresh(callback: types.CallbackQuery):
    session = _session(callback.message.chat.id)
    if session.result_filters is None:
        await callback.answer("Нечего обновлять — сделай новый поиск", show_alert=True)
        return
    await callback.answer()
    await _run_search(callback.message, session, session.result_filters.copy())


# ---------------------------------------------------------------- pagination

@router.callback_query(PageCb.filter())
async def on_page(callback: types.CallbackQuery, callback_data: PageCb):
    session = _session(callback.message.chat.id)
    if session.result is None or session.results_message_id != callback.message.message_id:
        # бот перезапускался или это старое сообщение — его выдачи в памяти уже нет
        await callback.answer("Эта выдача устарела, отправь запрос ещё раз", show_alert=True)
        with suppress(TelegramBadRequest):
            await callback.message.edit_reply_markup(reply_markup=None)
        return

    session.set_page(callback_data.page)
    text, keyboard = _render_results(session)
    await _safe_edit(callback.message, text, reply_markup=keyboard)
    await callback.answer()
