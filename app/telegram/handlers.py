from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import get_settings
from app.sniffers.hh.sniffer import HHSniffer
from app.sniffers.hh.query import HHQuery, Experience, WorkFormat, EmploymentForm
from app.telegram.formater import format_vacancies
from app.telegram.pagination import PaginationState

router = Router()

WORK_FORMATS = ["REMOTE", "HYBRID", "ON_SITE"]
EMPLOYMENT_FORMS = ["FULL", "PART"]
EXPERIENCES = ["NO_EXP", "1_3", "3_6", "6+"]

EXPERIENCE_MAP = {
    "NO_EXP": Experience.NO_EXPERIENCE,
    "1_3": Experience.BETWEEN_1_AND_3,
    "3_6": Experience.BETWEEN_3_AND_6,
    "6+": Experience.MORE_THAN_6,
}

_filter_states: dict[int, dict] = {}

_pagination_states: dict[int, PaginationState] = {}


def _get_filter_state(chat_id: int) -> dict:
    if chat_id not in _filter_states:
        _filter_states[chat_id] = {
            "work_formats": set(),
            "employment_forms": set(),
            "experiences": set(),
            "labels": set(),
            "text": "",
            "query_text": "",
        }
    return _filter_states[chat_id]


def _get_pagination(chat_id: int) -> PaginationState:
    if chat_id not in _pagination_states:
        _pagination_states[chat_id] = PaginationState()
    return _pagination_states[chat_id]


def _make_filter_buttons(category: str, items: list[str], filter_state: dict) -> InlineKeyboardMarkup:
    buttons = []
    for item in items:
        selected = item in filter_state.get(category, set())
        emoji = "✅" if selected else "⬜"
        buttons.append(
            InlineKeyboardButton(
                text=f"{emoji} {item}",
                callback_data=f"filter:{category}:{item}",
            )
        )
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def _make_search_keyboard(state: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔍 Искать",
            callback_data="search",
        )]
    ])


def _make_pagination_keyboard(chat_id: int, page: int, total: int) -> InlineKeyboardMarkup:
    pages = max(1, (total + 2) // 3) if total > 2 else 1
    buttons = []

    if page > 0:
        buttons.append(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"page:{chat_id}:{page - 1}",
        ))

    if page < pages - 1:
        buttons.append(InlineKeyboardButton(
            text="Вперёд ▶️",
            callback_data=f"page:{chat_id}:{page + 1}",
        ))

    if not buttons:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Показать фильтры", callback_data=f"filters:{chat_id}")]
        ])

    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def _build_filter_keyboard(filter_state: dict) -> InlineKeyboardMarkup:
    rows = []

    rows.append(_make_filter_buttons("work_formats", WORK_FORMATS, filter_state).inline_keyboard[0])
    rows.append([])

    rows.append(_make_filter_buttons("employment_forms", EMPLOYMENT_FORMS, filter_state).inline_keyboard[0])
    rows.append([])

    rows.append(_make_filter_buttons("experiences", EXPERIENCES, filter_state).inline_keyboard[0])
    rows.append([])

    rows.append(_make_search_keyboard(filter_state).inline_keyboard[0])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def _build_query_from_filter_state(chat_id: int) -> HHQuery:
    filter_state = _get_filter_state(chat_id)
    experiences = tuple(
        EXPERIENCE_MAP[e] for e in filter_state.get("experiences", set()) if e in EXPERIENCE_MAP
    )
    work_formats = tuple(
        WorkFormat(f) for f in filter_state.get("work_formats", set()) if f in WorkFormat.__members__
    )
    employment_forms = tuple(
        EmploymentForm(f) for f in filter_state.get("employment_forms", set()) if f in EmploymentForm.__members__
    )

    return HHQuery(
        text=filter_state.get("text") or filter_state.get("query_text", ""),
        experience=experiences,
        work_format=work_formats,
        employment_form=employment_forms,
    )


async def _search_vacancies(chat_id: int) -> list[dict]:
    query = _build_query_from_filter_state(chat_id)
    if not query.text:
        return []

    sniffer = HHSniffer(get_settings())
    try:
        await sniffer.start()
        vacancies = await sniffer.fetch_vacancies(query)
        return vacancies
    finally:
        await sniffer.stop()


async def _send_results(chat_id: int, message: types.Message):
    pagination = _get_pagination(chat_id)
    page_vacancies = pagination.get_page_vacancies()
    total = pagination.total
    page = pagination.current_page
    query_text = _get_filter_state(chat_id).get("query_text", "")

    formatted = format_vacancies(page_vacancies, query_text, page, total)
    keyboard = _make_pagination_keyboard(chat_id, page, total)

    await message.answer(formatted, reply_markup=keyboard)


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    chat_id = message.chat.id
    filter_state = _get_filter_state(chat_id)
    keyboard = _build_filter_keyboard(filter_state)
    await message.answer(
        "🔎 Job Sniffer\n\nВыберите фильтры, затем нажмите «Искать» и введите текст запроса.",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("filter:"))
async def handle_filter(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    category, item = parts[1], parts[2]

    filter_state = _get_filter_state(callback.from_user.id)

    if category not in filter_state:
        filter_state[category] = set()

    if item in filter_state[category]:
        filter_state[category].remove(item)
    else:
        filter_state[category].add(item)

    keyboard = _build_filter_keyboard(filter_state)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data == "search")
async def handle_search(callback: types.CallbackQuery):
    filter_state = _get_filter_state(callback.from_user.id)

    active = []
    if filter_state.get("work_formats"):
        active.append(f"Формат: {', '.join(filter_state['work_formats'])}")
    if filter_state.get("employment_forms"):
        active.append(f"Занятость: {', '.join(filter_state['employment_forms'])}")
    if filter_state.get("experiences"):
        active.append(f"Опыт: {', '.join(filter_state['experiences'])}")

    msg = "Введите текст поиска (например: Python):\n\n"
    if active:
        msg += "📌 Активные фильтры:\n" + "\n".join(f"  • {f}" for f in active)

    await callback.answer()
    await callback.message.answer(msg)


@router.callback_query(lambda c: c.data.startswith("page:"))
async def handle_pagination(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    chat_id = int(parts[1])
    page = int(parts[2])

    pagination = _get_pagination(chat_id)
    pagination.current_page = page

    page_vacancies = pagination.get_page_vacancies()
    total = pagination.total

    query_text = _get_filter_state(chat_id).get("query_text", "")
    formatted = format_vacancies(page_vacancies, query_text, page, total)
    keyboard = _make_pagination_keyboard(chat_id, page, total)

    await callback.message.edit_text(formatted, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("filters:"))
async def handle_show_filters(callback: types.CallbackQuery):
    chat_id = int(callback.data.split(":")[1])
    filter_state = _get_filter_state(chat_id)
    keyboard = _build_filter_keyboard(filter_state)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.message()
async def handle_text(message: types.Message):
    chat_id = message.chat.id

    pagination = _get_pagination(chat_id)
    filter_state = _get_filter_state(chat_id)

    filter_state["text"] = message.text
    filter_state["query_text"] = message.text
    pagination.current_page = 0
    pagination.vacancies = []
    pagination.total = 0

    searching_msg = await message.answer("⏳ Ищу вакансии, подождите...")

    try:
        vacancies = await _search_vacancies(chat_id)
        pagination.set_vacancies(vacancies, len(vacancies))

        # Форматируем и отправляем результаты
        await searching_msg.delete()
        await _send_results(chat_id, message)

    except Exception as e:
        error_text = f"❌ Ошибка при поиске:\n\n{e}"
        if len(error_text) > 4000:
            error_text = error_text[:3997] + "\n… (сообщение обрезано)"
        try:
            await searching_msg.edit_text(error_text)
        except Exception:
            await message.answer(error_text)
