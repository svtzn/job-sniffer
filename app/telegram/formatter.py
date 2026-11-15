"""Тексты сообщений бота (parse_mode=HTML)."""

from html import escape

from app.services.search import SearchFilters
from app.sniffers.schemas import Salary, SearchResult, VacancyData
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


def format_filters_summary(filters: SearchFilters) -> str:
    """Короткая строка вида «Удалённо, Гибрид · 1–3 года · Россия · с ЗП»."""
    parts: list[str] = []
    if filters.work_formats:
        parts.append(", ".join(WORK_FORMAT_LABELS[f.value] for f in sorted(filters.work_formats, key=lambda f: f.value)))
    if filters.employment_forms:
        parts.append(", ".join(EMPLOYMENT_LABELS[e.value] for e in sorted(filters.employment_forms, key=lambda e: e.value)))
    if filters.experiences:
        parts.append(", ".join(EXPERIENCE_LABELS[e.value] for e in sorted(filters.experiences, key=lambda e: e.value)))
    parts.append(filters.area)
    if filters.only_with_salary:
        parts.append("только с ЗП")
    return " · ".join(parts)


def format_filters_panel(filters: SearchFilters) -> str:
    query = f"<b>{escape(filters.text)}</b>" if filters.text else "<i>не задан</i>"
    return (
        "⚙️ <b>Фильтры поиска</b>\n\n"
        f"🔤 Запрос: {query}\n"
        f"🎛 {escape(format_filters_summary(filters))}\n\n"
        "Отметь нужное кнопками и просто отправь мне текст запроса "
        "(например, <code>python junior</code>) — я поищу с этими фильтрами."
    )


def format_vacancy(index: int, v: VacancyData) -> str:
    title = v.title if len(v.title) <= _MAX_TITLE else v.title[:_MAX_TITLE - 1] + "…"
    lines = [f"<b>{index}. <a href=\"{escape(v.url, quote=True)}\">{escape(title)}</a></b>"]

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

    return "\n".join(lines)


def format_results_page(
    result: SearchResult,
    filters: SearchFilters,
    vacancies: list[VacancyData],
    page: int,
    pages: int,
    page_size: int,
) -> str:
    header = [f"🔍 <b>«{escape(filters.text)}»</b>"]
    header.append(f"🎛 {escape(format_filters_summary(filters))}")

    if not result.vacancies:
        header.append("")
        header.append("Ничего не нашлось 😔 Попробуй другой запрос или ослабь фильтры.")
        return "\n".join(header)

    found = f"Найдено на HH: <b>{_num(result.total_found)}</b>" if result.total_found else "Найдено"
    header.append(f"{found} · загружено {len(result.vacancies)}")
    if pages > 1:
        header.append(f"Страница {page + 1}/{pages}")

    cards = [format_vacancy(page * page_size + i, v) for i, v in enumerate(vacancies, 1)]
    text = "\n".join(header) + "\n\n" + "\n\n".join(cards)

    if len(text) > TELEGRAM_LIMIT:  # страховка; при 5 карточках на страницу не срабатывает
        text = text[:TELEGRAM_LIMIT - 1] + "…"
    return text


def format_error(error: Exception) -> str:
    text = str(error) or error.__class__.__name__
    if len(text) > 500:
        text = text[:500] + "…"
    return f"❌ Не получилось выполнить поиск:\n<code>{escape(text)}</code>\n\nПопробуй ещё раз чуть позже."
