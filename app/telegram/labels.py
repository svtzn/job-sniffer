"""Человекочитаемые подписи для кодов HH. Используются и в кнопках, и в карточках."""

from app.sniffers.hh.query import EmploymentForm, Experience, WorkFormat

WORK_FORMAT_LABELS: dict[str, str] = {
    WorkFormat.REMOTE.value: "Удалённо",
    WorkFormat.HYBRID.value: "Гибрид",
    WorkFormat.ON_SITE.value: "Офис",
    WorkFormat.FIELD_WORK.value: "Разъездная",
}

EMPLOYMENT_LABELS: dict[str, str] = {
    EmploymentForm.FULL.value: "Полная",
    EmploymentForm.PART.value: "Частичная",
    EmploymentForm.PROJECT.value: "Проект/подработка",
    EmploymentForm.FLY_IN_FLY_OUT.value: "Вахта",
}

EXPERIENCE_LABELS: dict[str, str] = {
    Experience.NO_EXPERIENCE.value: "Без опыта",
    Experience.BETWEEN_1_AND_3.value: "1–3 года",
    Experience.BETWEEN_3_AND_6.value: "3–6 лет",
    Experience.MORE_THAN_6.value: "6+ лет",
}

CURRENCY_SYMBOLS: dict[str, str] = {
    "RUR": "₽",
    "RUB": "₽",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "KZT": "₸",
    "UAH": "₴",
    "AZN": "₼",
    "BYR": "Br",
    "UZS": "сум",
    "KGS": "сом",
    "GEL": "₾",
}

SALARY_MODE_SUFFIX: dict[str, str] = {
    "MONTH": "",
    "HOUR": "/час",
    "SHIFT": "/смена",
    "FLY_IN_FLY_OUT": "/вахта",
    "SERVICE": "/услуга",
}
