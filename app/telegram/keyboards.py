from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.services.filters import AREAS, MAX_LOCATIONS, SearchFilters, area_name
from app.sniffers.hh.query import EmploymentForm, Experience, WorkFormat
from app.telegram.formatter import format_location
from app.telegram.labels import EMPLOYMENT_LABELS, EXPERIENCE_LABELS, WORK_FORMAT_LABELS

ANY_AREA = "any"  # значение для area_id=None в callback_data


class FilterCb(CallbackData, prefix="f"):
    group: str  # emp | exp | salary
    value: str = ""


class LocCb(CallbackData, prefix="l"):
    action: str  # open | area | wf | del | done | add | preset
    idx: int = 0
    value: str = ""


class ActionCb(CallbackData, prefix="a"):
    action: str  # search | reset | filters | refresh | noop


class PageCb(CallbackData, prefix="p"):
    page: int


def _btn(text: str, cb: CallbackData) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=cb.pack())


def _toggle(text: str, selected: bool, cb: CallbackData) -> InlineKeyboardButton:
    return _btn(f"{'✅' if selected else '▫️'} {text}", cb)


def _chunks(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


# ---------------------------------------------------------------- панель фильтров

def filters_keyboard(filters: SearchFilters, home_area_id: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for i, rule in enumerate(filters.locations):
        prefix = f"{i + 1}. " if len(filters.locations) > 1 else ""
        rows.append([_btn(f"📍 {prefix}{format_location(rule)} ✏️", LocCb(action="open", idx=i))])

    loc_row = []
    if len(filters.locations) < MAX_LOCATIONS:
        loc_row.append(_btn("➕ Локация", LocCb(action="add")))
    loc_row.append(_btn(f"🏠 Удалёнка + {area_name(home_area_id)}", LocCb(action="preset")))
    rows.append(loc_row)

    rows.append([
        _toggle(EMPLOYMENT_LABELS[e.value], e in filters.employment_forms, FilterCb(group="emp", value=e.value))
        for e in (EmploymentForm.FULL, EmploymentForm.PART, EmploymentForm.PROJECT)
    ])
    exp_buttons = [
        _toggle(EXPERIENCE_LABELS[e.value], e in filters.experiences, FilterCb(group="exp", value=e.value))
        for e in Experience
    ]
    rows.extend(_chunks(exp_buttons, 2))
    rows.append([_toggle("Только с ЗП", filters.only_with_salary, FilterCb(group="salary"))])
    rows.append([
        _btn("🔍 Искать", ActionCb(action="search")),
        _btn("🧹 Сбросить", ActionCb(action="reset")),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------- редактор локации

def area_options(home_area_id: int) -> list[int | None]:
    options = list(AREAS)
    if home_area_id not in options:
        options.insert(-1, home_area_id)  # перед «Везде»
    return options


def encode_area(area_id: int | None) -> str:
    return ANY_AREA if area_id is None else str(area_id)


def decode_area(value: str) -> int | None:
    return None if value == ANY_AREA else int(value)


def location_editor_keyboard(filters: SearchFilters, index: int, home_area_id: int) -> InlineKeyboardMarkup:
    rule = filters.locations[index]

    area_buttons = [
        _btn(f"{'🔘' if rule.area_id == a else '⚪'} {area_name(a)}", LocCb(action="area", idx=index, value=encode_area(a)))
        for a in area_options(home_area_id)
    ]
    rows = _chunks(area_buttons, 3)

    rows.append([
        _toggle(WORK_FORMAT_LABELS[f.value], f in rule.work_formats, LocCb(action="wf", idx=index, value=f.value))
        for f in (WorkFormat.REMOTE, WorkFormat.HYBRID, WorkFormat.ON_SITE)
    ])

    last_row = []
    if len(filters.locations) > 1:
        last_row.append(_btn("🗑 Удалить", LocCb(action="del", idx=index)))
    last_row.append(_btn("✅ Готово", LocCb(action="done")))
    rows.append(last_row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------- выдача

def results_keyboard(page: int, pages: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    noop = ActionCb(action="noop")

    if pages > 1:
        rows.append([
            _btn("◀️" if page > 0 else "·", PageCb(page=page - 1) if page > 0 else noop),
            _btn(f"{page + 1}/{pages}", noop),
            _btn("▶️" if page < pages - 1 else "·", PageCb(page=page + 1) if page < pages - 1 else noop),
        ])

    rows.append([
        _btn("🔄 Обновить", ActionCb(action="refresh")),
        _btn("⚙️ Фильтры", ActionCb(action="filters")),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)
