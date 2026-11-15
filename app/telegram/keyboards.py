from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.services.search import AREAS, SearchFilters
from app.sniffers.hh.query import EmploymentForm, Experience, WorkFormat
from app.telegram.labels import EMPLOYMENT_LABELS, EXPERIENCE_LABELS, WORK_FORMAT_LABELS


class FilterCb(CallbackData, prefix="f"):
    group: str  # wf | emp | exp | area | salary
    value: str = ""


class ActionCb(CallbackData, prefix="a"):
    action: str  # search | reset | filters | refresh | noop


class PageCb(CallbackData, prefix="p"):
    page: int


def _toggle(text: str, selected: bool, cb: CallbackData) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=f"{'✅' if selected else '▫️'} {text}", callback_data=cb.pack())


def filters_keyboard(filters: SearchFilters) -> InlineKeyboardMarkup:
    work_formats = [WorkFormat.REMOTE, WorkFormat.HYBRID, WorkFormat.ON_SITE]
    employment = [EmploymentForm.FULL, EmploymentForm.PART, EmploymentForm.PROJECT]
    experiences = list(Experience)

    rows = [
        [_toggle(WORK_FORMAT_LABELS[f.value], f in filters.work_formats, FilterCb(group="wf", value=f.value))
         for f in work_formats],
        [_toggle(EMPLOYMENT_LABELS[e.value], e in filters.employment_forms, FilterCb(group="emp", value=e.value))
         for e in employment],
        [_toggle(EXPERIENCE_LABELS[e.value], e in filters.experiences, FilterCb(group="exp", value=e.value))
         for e in experiences[:2]],
        [_toggle(EXPERIENCE_LABELS[e.value], e in filters.experiences, FilterCb(group="exp", value=e.value))
         for e in experiences[2:]],
        [
            InlineKeyboardButton(text=f"📍 {filters.area}", callback_data=FilterCb(group="area").pack()),
            _toggle("Только с ЗП", filters.only_with_salary, FilterCb(group="salary")),
        ],
        [
            InlineKeyboardButton(text="🔍 Искать", callback_data=ActionCb(action="search").pack()),
            InlineKeyboardButton(text="🧹 Сбросить", callback_data=ActionCb(action="reset").pack()),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def next_area(current: str) -> str:
    names = list(AREAS)
    idx = names.index(current) if current in names else -1
    return names[(idx + 1) % len(names)]


def results_keyboard(page: int, pages: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    if pages > 1:
        nav = []
        nav.append(InlineKeyboardButton(
            text="◀️" if page > 0 else "·",
            callback_data=(PageCb(page=page - 1) if page > 0 else ActionCb(action="noop")).pack(),
        ))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data=ActionCb(action="noop").pack()))
        nav.append(InlineKeyboardButton(
            text="▶️" if page < pages - 1 else "·",
            callback_data=(PageCb(page=page + 1) if page < pages - 1 else ActionCb(action="noop")).pack(),
        ))
        rows.append(nav)

    rows.append([
        InlineKeyboardButton(text="🔄 Обновить", callback_data=ActionCb(action="refresh").pack()),
        InlineKeyboardButton(text="⚙️ Фильтры", callback_data=ActionCb(action="filters").pack()),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)
