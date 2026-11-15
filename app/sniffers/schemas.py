"""Нормализованные данные, которые сниффер отдаёт наружу (боту, матчеру, ИИ).

Источник-специфичные детали (разметка HH, его JSON) сюда не протекают.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class Salary:
    amount_from: int | None = None
    amount_to: int | None = None
    currency: str | None = None  # RUR, USD, EUR, KZT, UZS ...
    gross: bool | None = None  # True — до вычета налогов
    mode: str | None = None  # MONTH, HOUR, SHIFT, ...

    @property
    def is_specified(self) -> bool:
        return self.amount_from is not None or self.amount_to is not None


@dataclass(slots=True)
class VacancyData:
    id: str
    title: str
    url: str
    source: str = "hh_ru"

    employer: str | None = None
    employer_trusted: bool = False
    employer_rating: float | None = None

    salary: Salary = field(default_factory=Salary)
    experience: str | None = None  # noExperience / between1And3 / between3And6 / moreThan6
    work_formats: list[str] = field(default_factory=list)  # REMOTE / HYBRID / ON_SITE / FIELD_WORK
    employment_form: str | None = None  # FULL / PART / PROJECT / FLY_IN_FLY_OUT
    area: str | None = None  # город/регион вакансии
    address: str | None = None
    published_at: datetime | None = None
    responses_count: int | None = None
    is_internship: bool = False
    is_ad: bool = False  # рекламное размещение в выдаче


@dataclass(slots=True)
class PageResult:
    """Одна страница выдачи источника."""

    vacancies: list[VacancyData]
    total_found: int | None = None  # сколько всего нашёл источник
    last_page: int | None = None  # индекс последней страницы (0-based)


@dataclass(slots=True)
class SearchResult:
    """Итог поиска по нескольким страницам."""

    vacancies: list[VacancyData]
    total_found: int | None = None
