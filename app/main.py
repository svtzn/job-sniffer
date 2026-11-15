"""Ручной прогон поиска без Telegram: python -m app.main"""

import asyncio
import logging

from app.config import get_settings
from app.services.filters import SearchFilters
from app.services.search import search_vacancies
from app.telegram.formatter import format_location, format_salary


async def main():
    logging.basicConfig(level=logging.INFO)
    filters = SearchFilters(text="python")
    filters.apply_remote_plus_home(get_settings().home_area_id)  # удалёнка + мой город

    try:
        result = await search_vacancies(filters, limit=40)
    except PermissionError as e:
        print(f"[ERROR] Не удалось запустить браузер: {e}")
        print("Проверь: антивирус / групповые политики блокируют subprocess.")
        return

    for loc in result.locations:
        print(f"{format_location(loc.rule)}: найдено {loc.total_found}, загружено {loc.fetched}")
    print(f"Итого без повторов: {len(result.vacancies)}")
    for v in result.vacancies:
        where = ", ".join(format_location(result.locations[i].rule) for i in result.matched_locations[v.id])
        print(f"- {v.title} | {v.employer} | {v.area} | {format_salary(v.salary) or 'з/п не указана'} | {where}")


if __name__ == "__main__":
    asyncio.run(main())
