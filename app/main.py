"""Ручной прогон сниффера без Telegram: python -m app.main"""

import asyncio
import logging

from app.services.search import SearchFilters, search_vacancies
from app.sniffers.hh.query import WorkFormat
from app.telegram.formatter import format_salary


async def main():
    logging.basicConfig(level=logging.INFO)
    filters = SearchFilters(text="fastapi", work_formats={WorkFormat.REMOTE}, only_with_salary=True)

    try:
        result = await search_vacancies(filters, limit=20)
    except PermissionError as e:
        print(f"[ERROR] Не удалось запустить браузер: {e}")
        print("Проверь: антивирус / групповые политики блокируют subprocess.")
        return

    print(f"Найдено на HH: {result.total_found}, загружено: {len(result.vacancies)}")
    for v in result.vacancies:
        print(f"- {v.title} | {v.employer} | {format_salary(v.salary) or 'з/п не указана'} | {v.url}")


if __name__ == "__main__":
    asyncio.run(main())
