"""Тексты сообщений бота (parse_mode=HTML)."""

from html import escape

from app.services.filters import LocationRule, SearchFilters
from app.services.saved_filters import MAX_NAME_LENGTH, SavedFilterInfo
from app.services.search import SearchOutcome
from app.sniffers.schemas import Salary, VacancyData
from app.telegram.labels import (
    CURRENCY_SYMBOLS,
    EMPLOYMENT_LABELS,
    EXPERIENCE_LABELS,
    SALARY_MODE_SUFFIX,
    WORK_FORMAT_LABELS,
)

TELEGRAM_LIMIT = 4096
_MAX_TITLE = 120


def _num(value: int) -> str:
    return f"{value:,}".replace(",", " ")  # неразрывный пробел: 150 000


def format_salary(salary: Salary) -> str | None:
    if not salary.is_specified:
        return None

    lo, hi = salary.amount_from, salary.amount_to
    if lo is not None and hi is not None:
        amount = _num(lo) if lo == hi else f"{_num(lo)} – {_num(hi)}"
    elif lo is not None:
        amount = f"от {_num(lo)}"
    else:
        amount = f"до {_num(hi)}"

    currency = CURRENCY_SYMBOLS.get(salary.currency or "", salary.currency or "")
    text = f"{amount} {currency}".strip()
    text += SALARY_MODE_SUFFIX.get(salary.mode or "", "")
    if salary.gross is True:
        text += " до вычета"
    elif salary.gross is False:
        text += " на руки"
    return text


def format_location(rule: LocationRule) -> str:
    """«Россия · Удалённо», «Краснодар · Офис, Гибрид», «Москва · любой формат»."""
    formats = rule.ordered_work_formats()
    fmt = ", ".join(WORK_FORMAT_LABELS[f.value] for f in formats) if formats else "любой формат"
    return f"{rule.area_name} · {fmt}"


def format_common_summary(filters: SearchFilters) -> str:
    """Общая часть фильтра: «Полная · 1–3 года · только с ЗП» или «без доп. условий»."""
    parts: list[str] = []
    if filters.employment_forms:
        employment = sorted(filters.employment_forms, key=lambda e: e.value)
        parts.append(", ".join(EMPLOYMENT_LABELS[e.value] for e in employment))
    if filters.experiences:
        parts.append(", ".join(EXPERIENCE_LABELS[e.value] for e in sorted(filters.experiences, key=lambda e: e.value)))
    if filters.only_with_salary:
        parts.append("только с ЗП")
    if filters.exclude_words:
        parts.append("без: " + ", ".join(filters.exclude_words))
    return " · ".join(parts) or "без доп. условий"


def _locations_block(filters: SearchFilters) -> str:
    if len(filters.locations) == 1:
        return f"📍 {escape(format_location(filters.locations[0]))}"
    lines = ["📍 Локации (выдача объединяется):"]
    lines += [f"   {i}. {escape(format_location(r))}" for i, r in enumerate(filters.locations, 1)]
    return "\n".join(lines)


def format_filters_panel(filters: SearchFilters, saved_name: str | None = None, modified: bool = False) -> str:
    query = f"<b>{escape(filters.text)}</b>" if filters.text else "<i>не задан</i>"
    saved = ""
    if saved_name:
        saved = f"📂 Сохранённый фильтр: <b>{escape(saved_name)}</b>"
        saved += " <i>(изменён, не сохранено)</i>\n" if modified else "\n"
    return (
        "⚙️ <b>Фильтры поиска</b>\n\n"
        f"{saved}"
        f"🔤 Запрос: {query}\n"
        f"{_locations_block(filters)}\n"
        f"🎛 {escape(format_common_summary(filters))}\n\n"
        "Нажми на локацию, чтобы изменить регион и формат, или добавь ещё одну — "
        "например, удалёнка по России + офис в своём городе.\n"
        "Потом просто отправь текст запроса (например, <code>python junior</code>)."
    )


def default_filter_name(filters: SearchFilters) -> str:
    """«python · Россия · Удалённо + Краснодар · Гибрид, Офис» (обрезается до лимита)."""
    name = f"{filters.text.strip()} · " + " + ".join(format_location(r) for r in filters.locations)
    return name if len(name) <= MAX_NAME_LENGTH else name[: MAX_NAME_LENGTH - 1] + "…"


def format_saved_list(items: list[SavedFilterInfo]) -> str:
    if not items:
        return "📂 <b>Мои фильтры</b>\n\nПока пусто. Настрой фильтр в /filters, задай запрос и нажми «💾 Сохранить»."
    lines = ["📂 <b>Мои фильтры</b>", ""]
    for i, item in enumerate(items, 1):
        f = item.filters
        where = format_location(f.locations[0]) if len(f.locations) == 1 else f"{len(f.locations)} локации"
        bell = " 🔔" if item.is_subscribed else ""
        lines.append(f"{i}. <b>{escape(item.name)}</b>{bell}")
        lines.append(f"   «{escape(f.text)}» · {escape(where)} · {escape(format_common_summary(f))}")
    lines += [
        "",
        "▶️ — искать, 🔔/🔕 — подписка на новые вакансии, ✏️ — открыть в панели, 🗑 — удалить",
    ]
    return "\n".join(lines)


def format_delete_confirm(item: SavedFilterInfo) -> str:
    return f"🗑 Удалить фильтр <b>{escape(item.name)}</b>?\n\nЭто действие нельзя отменить."


def format_rename_prompt(item: SavedFilterInfo) -> str:
    return f"✏️ Новое название для <b>{escape(item.name)}</b>?\nОтправь его сообщением (до {MAX_NAME_LENGTH} символов)."


def format_location_editor(filters: SearchFilters, index: int) -> str:
    rule = filters.locations[index]
    return (
        f"📍 <b>Локация {index + 1}</b>: {escape(format_location(rule))}\n\n"
        "Выбери регион и форматы работы. Если формат не отмечен — подходит любой."
    )


def format_vacancy(index: int | None, v: VacancyData, location_labels: list[str] | None = None) -> str:
    title = v.title if len(v.title) <= _MAX_TITLE else v.title[: _MAX_TITLE - 1] + "…"
    number = f"{index}. " if index is not None else ""
    lines = [f'<b>{number}<a href="{escape(v.url, quote=True)}">{escape(title)}</a></b>']

    salary = format_salary(v.salary)
    lines.append(f"💰 {escape(salary)}" if salary else "💰 <i>з/п не указана</i>")

    if v.employer:
        employer = escape(v.employer)
        if v.employer_trusted:
            employer += " ✔️"
        if v.employer_rating:
            employer += f" · ★ {v.employer_rating:.1f}"
        lines.append(f"🏢 {employer}")

    place = [escape(v.area)] if v.area else []
    if v.work_formats:
        place.append(", ".join(WORK_FORMAT_LABELS.get(f, f) for f in v.work_formats))
    if place:
        lines.append("📍 " + " · ".join(place))

    meta = []
    if v.experience:
        meta.append(EXPERIENCE_LABELS.get(v.experience, v.experience))
    if v.published_at:
        meta.append(f"🗓 {v.published_at:%d.%m}")
    if v.responses_count is not None:
        meta.append(f"👥 {v.responses_count}")
    if v.is_internship:
        meta.append("стажировка")
    if meta:
        lines.append("📈 " + " · ".join(meta))

    if location_labels:
        lines.append("🎯 " + escape(" | ".join(location_labels)))

    return "\n".join(lines)


def format_results_page(
    result: SearchOutcome,
    filters: SearchFilters,
    vacancies: list[VacancyData],
    page: int,
    pages: int,
    page_size: int,
    saved_name: str | None = None,
) -> str:
    multi = len(result.locations) > 1
    header = [f"📂 {escape(saved_name)}"] if saved_name else []
    header.append(f"🔍 <b>«{escape(filters.text)}»</b>")
    if not multi:
        header.append(f"📍 {escape(format_location(filters.locations[0]))}")
    header.append(f"🎛 {escape(format_common_summary(filters))}")

    if multi:
        header.append("Найдено на HH:")
        for i, loc in enumerate(result.locations, 1):
            total = _num(loc.total_found) if loc.total_found is not None else "?"
            header.append(f"   {i}. {escape(format_location(loc.rule))} — <b>{total}</b>")

    if not result.vacancies:
        header.append("")
        header.append("Ничего не нашлось 😔 Попробуй другой запрос или ослабь фильтры.")
        return "\n".join(header)

    if multi:
        header.append(f"Загружено {len(result.vacancies)} без повторов, локации вперемешку")
    else:
        found = f"Найдено на HH: <b>{_num(result.total_found)}</b>" if result.total_found else "Найдено"
        header.append(f"{found} · загружено {len(result.vacancies)}")
    if result.excluded:
        header.append(f"🚫 Скрыто по исключённым словам: {result.excluded}")
    if pages > 1:
        header.append(f"Страница {page + 1}/{pages}")

    cards = []
    for i, v in enumerate(vacancies, 1):
        labels = None
        if multi:
            matched = sorted(result.matched_locations.get(v.id, []))
            labels = [format_location(result.locations[idx].rule) for idx in matched]
        cards.append(format_vacancy(page * page_size + i, v, labels))

    text = "\n".join(header) + "\n\n" + "\n\n".join(cards)
    if len(text) > TELEGRAM_LIMIT:  # страховка; при 5 карточках на страницу не срабатывает
        text = text[: TELEGRAM_LIMIT - 1] + "…"
    return text


def format_error(error: Exception) -> str:
    text = str(error) or error.__class__.__name__
    if len(text) > 500:
        text = text[:500] + "…"
    return f"❌ Не получилось выполнить поиск:\n<code>{escape(text)}</code>\n\nПопробуй ещё раз чуть позже."


# ---------------------------------------------------------------- подписки


def format_exclude_prompt(filters: SearchFilters) -> str:
    current = ", ".join(filters.exclude_words) if filters.exclude_words else "нет"
    return (
        "🚫 <b>Исключить слова</b>\n\n"
        "Вакансии, в названии которых есть любое из этих слов, не попадут в выдачу и подписки.\n"
        f"Сейчас: <i>{escape(current)}</i>\n\n"
        "Отправь слова через запятую, например <code>senior, lead, 1С, стажёр</code>.\n"
        "Отправь <code>-</code>, чтобы очистить список."
    )


def format_subscription_on(name: str, interval_minutes: int) -> str:
    return (
        f"🔔 Подписка на <b>{escape(name)}</b> включена.\n\n"
        f"Проверяю каждые {interval_minutes} мин. Сейчас запомню текущую выдачу — "
        "присылать буду только то, что появится после этого."
    )


def format_notification(v: VacancyData, filter_names: list[str]) -> str:
    text = "🔥 <b>Новая вакансия</b>\n\n" + format_vacancy(None, v)
    if filter_names:
        text += "\n\n🎯 Подходит: " + escape(", ".join(filter_names))
    return text


def format_digest(items: list[tuple[VacancyData, list[str]]]) -> str:
    """Сводка, когда новых вакансий много (или накопились за тихие часы)."""
    header = f"🔥 <b>Новых вакансий: {len(items)}</b>\n"
    lines: list[str] = []
    length = len(header)
    previous_filters: list[str] | None = None
    for shown, (v, filter_names) in enumerate(items):
        line = f'• <a href="{escape(v.url, quote=True)}">{escape(v.title[:_MAX_TITLE])}</a>'
        if v.employer:
            line += f" — {escape(v.employer)}"
        salary = format_salary(v.salary)
        if salary:
            line += f" · {escape(salary)}"
        if filter_names != previous_filters:
            line += f"\n   🎯 {escape(', '.join(filter_names))}"
            previous_filters = filter_names
        if length + len(line) + 60 > TELEGRAM_LIMIT:
            lines.append(f"\n…и ещё {len(items) - shown}")
            break
        lines.append(line)
        length += len(line) + 1
    return header + "\n".join(lines)


def format_hh_unavailable(name: str) -> str:
    return (
        f"⚠️ Не получается проверить подписку <b>{escape(name)}</b> — HH не отвечает "
        "несколько раз подряд. Продолжу пробовать и напишу, когда появятся новые вакансии."
    )
