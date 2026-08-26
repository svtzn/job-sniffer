from dataclasses import dataclass, fields
from enum import Enum
from urllib.parse import urlencode

# Будет заменено на self.config.hh_base_url при необходимости
_BASE_URL = "https://krasnodar.hh.ru/search/vacancy"


class Experience(str, Enum):
    NO_EXPERIENCE = "noExperience"
    BETWEEN_1_AND_3 = "between1And3"
    BETWEEN_3_AND_6 = "between3And6"
    MORE_THAN_6 = "moreThan6"


class WorkFormat(str, Enum):
    ON_SITE = "ON_SITE"
    FIELD_WORK = "FIELD_WORK"
    HYBRID = "HYBRID"
    REMOTE = "REMOTE"


class EmploymentForm(str, Enum):
    FULL = "FULL"
    FLY_IN_FLY_OUT = "FLY_IN_FLY_OUT"  # Вахта
    PART = "PART"
    PROJECT = "PROJECT"  # Подработка


class Label(str, Enum):
    # Employment_form additional labels
    accept_labor_contract = "accept_labor_contract"  # Трудовой договор
    internship = "internship"  # Стажировка

    # salary addutional labels
    with_salary = "with_salary"


class SearchField(str, Enum):
    # Где будет искать слова из text
    name = "name"  # title вакансии
    company_name = "company_name"
    description = "description"


@dataclass
class HHQuery:
    text: str | None = None
    experience: tuple[Experience, ...] = ()
    work_format: tuple[WorkFormat, ...] = ()
    employment_form: tuple[EmploymentForm, ...] = ()
    area: int | None = None
    salary: int | None = None
    label: tuple[Label, ...] = ()
    search_field: tuple[SearchField, ...] = ()
    page: int = 0
    items_on_page: int = 20

    # Можно переопределить URL (по умолчанию берётся из модуля)
    base_url: str = _BASE_URL

    def get_params(self) -> dict:
        params = {}

        for field in fields(self):
            value = getattr(self, field.name)

            if not value:
                continue

            if isinstance(value, Enum):
                params[field.name] = value.value

            elif isinstance(value, tuple):
                params[field.name] = [v.value for v in value]

            elif isinstance(value, int):
                params[field.name] = str(value)

            elif isinstance(value, str):
                params[field.name] = value

        return params

    def get_url(self) -> str:
        params = self.get_params()
        query = urlencode(params, doseq=True)
        return f"{self.base_url}?{query}" if query else self.base_url
