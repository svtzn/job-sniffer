"""SQL по вакансиям. Бизнес-логика сюда не попадает — только чтение/запись."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.models import FilterVacancy, Vacancy
from app.models.filter_vacancy import STATUS_SEEN
from app.repositories.upsert import insert_for
from app.sniffers.schemas import VacancyData

# Поля, которые обновляются при повторной встрече вакансии (first_seen_at не трогаем)
_UPDATABLE = (
    "title",
    "url",
    "employer",
    "employer_trusted",
    "employer_rating",
    "salary_from",
    "salary_to",
    "salary_currency",
    "salary_gross",
    "salary_mode",
    "experience",
    "work_formats",
    "employment_form",
    "area",
    "address",
    "published_at",
    "responses_count",
    "is_internship",
    "last_seen_at",
)


def _row(v: VacancyData, now) -> dict:
    return {
        "source": v.source,
        "external_id": v.id,
        "title": v.title[:500],
        "url": v.url[:1000],
        "employer": v.employer,
        "employer_trusted": v.employer_trusted,
        "employer_rating": v.employer_rating,
        "salary_from": v.salary.amount_from,
        "salary_to": v.salary.amount_to,
        "salary_currency": v.salary.currency,
        "salary_gross": v.salary.gross,
        "salary_mode": v.salary.mode,
        "experience": v.experience,
        "work_formats": list(v.work_formats),
        "employment_form": v.employment_form,
        "area": v.area,
        "address": v.address,
        "published_at": v.published_at,
        "responses_count": v.responses_count,
        "is_internship": v.is_internship,
        "first_seen_at": now,
        "last_seen_at": now,
    }


async def upsert_vacancies(session: AsyncSession, vacancies: list[VacancyData]) -> dict[tuple[str, str], int]:
    """Вставляет новые и обновляет известные вакансии.

    Возвращает {(source, external_id): id в БД}.
    """
    if not vacancies:
        return {}

    now = utcnow()
    rows = list({(v.source, v.id): _row(v, now) for v in vacancies}.values())
    insert = insert_for(session)
    stmt = insert(Vacancy).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Vacancy.source, Vacancy.external_id],
        set_={name: getattr(stmt.excluded, name) for name in _UPDATABLE},
    ).returning(Vacancy.id, Vacancy.source, Vacancy.external_id)

    result = await session.execute(stmt)
    return {(source, external_id): vid for vid, source, external_id in result.all()}


async def mark_seen(session: AsyncSession, filter_id: int, vacancy_ids: list[int]) -> None:
    """Отмечает вакансии как уже виденные по фильтру (повторные отметки игнорируются)."""
    if not vacancy_ids:
        return
    insert = insert_for(session)
    now = utcnow()
    stmt = (
        insert(FilterVacancy)
        .values(
            [
                {"filter_id": filter_id, "vacancy_id": vid, "first_seen_at": now, "status": STATUS_SEEN}
                for vid in set(vacancy_ids)
            ]
        )
        .on_conflict_do_nothing(index_elements=[FilterVacancy.filter_id, FilterVacancy.vacancy_id])
    )
    await session.execute(stmt)
