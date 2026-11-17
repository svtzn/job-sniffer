import json

from app.sniffers.hh.parser import HHParser

STATE = {
    "vacancySearchResult": {
        "totalResults": 1234,
        "paging": {"lastPage": {"page": 61}},
        "vacancies": [
            {
                "vacancyId": 101,
                "name": "Python developer",
                "company": {"visibleName": "Ромашка", "@trusted": True, "employerReviews": {"totalRating": "4.5"}},
                "compensation": {"from": 150000, "to": 200000, "currencyCode": "RUR", "gross": False, "mode": "MONTH"},
                "workExperience": "between1And3",
                "workFormats": [{"workFormatsElement": ["REMOTE", "HYBRID"]}],
                "employmentForm": "FULL",
                "area": {"name": "Москва"},
                "publicationTime": {"$": "2026-11-13T18:52:21.191+03:00"},
                "responsesCount": 33,
                "links": {"desktop": "https://hh.ru/vacancy/101"},
                "@isAdv": True,
            },
            {"vacancyId": 102, "name": "Без зарплаты", "compensation": {"noCompensation": {}}},
        ],
    }
}


def _page(state: dict | None = None, cards: str = "") -> str:
    template = f'<template id="HH-Lux-InitialState">{json.dumps(state)}</template>' if state else ""
    return f"<html><body>{template}{cards}</body></html>"


def test_parses_embedded_json_state():
    result = HHParser().parse_page(_page(STATE))

    assert result.total_found == 1234
    assert result.last_page == 61
    v, no_salary = result.vacancies
    assert v.id == "101" and v.title == "Python developer" and v.url == "https://hh.ru/vacancy/101"
    assert v.employer == "Ромашка" and v.employer_trusted and v.employer_rating == 4.5
    salary = (v.salary.amount_from, v.salary.amount_to, v.salary.currency, v.salary.gross)
    assert salary == (150000, 200000, "RUR", False)
    assert v.work_formats == ["REMOTE", "HYBRID"]
    assert v.experience == "between1And3"
    assert v.published_at is not None and v.published_at.day == 13
    assert v.responses_count == 33 and v.is_ad
    assert not no_salary.salary.is_specified


def test_falls_back_to_html_cards():
    cards = """
    <div data-qa="vacancy-serp__vacancy">
      <a data-qa="serp-item__title" href="https://krasnodar.hh.ru/vacancy/555?query=py">
        <span data-qa="serp-item__title-text">Backend</span></a>
      <span data-qa="vacancy-serp__vacancy-employer-text">ООО Тест</span>
      <span data-qa="vacancy-serp__vacancy-address">Краснодар</span>
      <span data-qa="vacancy-serp__vacancy-work-experience-noExperience">Без опыта</span>
    </div>"""

    result = HHParser().parse_page(_page(None, cards))

    (v,) = result.vacancies
    assert v.id == "555" and v.title == "Backend" and v.employer == "ООО Тест"
    assert v.area == "Краснодар" and v.experience == "noExperience"
    assert v.url == "https://hh.ru/vacancy/555"


def test_empty_page():
    assert HHParser().parse_page(_page()).vacancies == []
