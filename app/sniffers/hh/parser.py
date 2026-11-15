"""Парсер страницы выдачи HH.ru.

HH отдаёт выдачу двумя способами одновременно:

1. ``<template id="HH-Lux-InitialState">`` — JSON-состояние страницы, из которого
   React рисует карточки. В нём есть всё в структурированном виде: зарплата
   от/до + валюта, форматы работы, опыт, дата публикации, число откликов,
   общее количество найденных вакансий и номер последней страницы.
2. HTML-карточки ``[data-qa="vacancy-serp__vacancy"]``.

Основной путь — JSON (точнее и устойчивее к редизайну вёрстки).
HTML-разбор оставлен как запасной вариант, если JSON пропадёт или сменит формат.
"""

import json
import logging
import re
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup, Tag

from app.sniffers.schemas import PageResult, Salary, VacancyData

logger = logging.getLogger(__name__)

_VACANCY_ID_RE = re.compile(r"/vacancy/(\d+)")
_CURRENCY_SYMBOLS = {"₽": "RUR", "$": "USD", "€": "EUR", "£": "GBP", "₸": "KZT", "₴": "UAH", "₼": "AZN"}


class HHParser:

    def parse_page(self, html: str) -> PageResult:
        soup = BeautifulSoup(html, "html.parser")

        result = self._parse_initial_state(soup)
        if result is not None and result.vacancies:
            return result

        logger.warning("HH: JSON-состояние не найдено или пустое, разбираю HTML-карточки")
        fallback = self._parse_html_cards(soup)
        if result is not None:
            # из JSON могли достать хотя бы total/last_page
            fallback.total_found = fallback.total_found or result.total_found
            fallback.last_page = fallback.last_page if fallback.last_page is not None else result.last_page
        return fallback

    # Обратная совместимость со старым API
    def parse_vacancies(self, html: str) -> list[VacancyData]:
        return self.parse_page(html).vacancies

    # ------------------------------------------------------------------ JSON

    def _parse_initial_state(self, soup: BeautifulSoup) -> PageResult | None:
        template = soup.select_one("template#HH-Lux-InitialState")
        if template is None:
            return None
        try:
            state = json.loads(template.text)
            search = state["vacancySearchResult"]
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.exception("HH: не удалось разобрать HH-Lux-InitialState")
            return None

        vacancies = []
        for raw in search.get("vacancies") or []:
            try:
                vacancies.append(self._vacancy_from_json(raw))
            except Exception:  # одна кривая карточка не должна ронять всю страницу
                logger.exception("HH: не удалось разобрать вакансию %s", raw.get("vacancyId"))

        paging = search.get("paging") or {}
        last_page = (paging.get("lastPage") or {}).get("page")
        if last_page is None:
            pages = [p.get("page") for p in paging.get("pages") or [] if isinstance(p.get("page"), int)]
            last_page = max(pages) if pages else 0

        return PageResult(
            vacancies=vacancies,
            total_found=_to_int(search.get("totalResults")),
            last_page=last_page,
        )

    def _vacancy_from_json(self, raw: dict[str, Any]) -> VacancyData:
        vacancy_id = str(raw["vacancyId"])
        company = raw.get("company") or {}
        reviews = company.get("employerReviews") or {}
        comp = raw.get("compensation") or {}
        area = raw.get("area") or {}
        address = raw.get("address") or {}

        work_formats: list[str] = []
        for group in raw.get("workFormats") or []:
            work_formats.extend(group.get("workFormatsElement") or [])

        url = (raw.get("links") or {}).get("desktop") or f"https://hh.ru/vacancy/{vacancy_id}"

        return VacancyData(
            id=vacancy_id,
            title=(raw.get("name") or "").strip(),
            url=url,
            employer=company.get("visibleName") or company.get("name"),
            employer_trusted=bool(company.get("@trusted")),
            employer_rating=_to_float(reviews.get("totalRating")),
            salary=Salary(
                amount_from=_to_int(comp.get("from")),
                amount_to=_to_int(comp.get("to")),
                currency=comp.get("currencyCode"),
                gross=comp.get("gross"),
                mode=comp.get("mode"),
            ),
            experience=raw.get("workExperience"),
            work_formats=work_formats,
            employment_form=raw.get("employmentForm"),
            area=area.get("name"),
            address=address.get("displayName"),
            published_at=_parse_dt((raw.get("publicationTime") or {}).get("$")),
            responses_count=_to_int(raw.get("responsesCount")),
            is_internship=bool(raw.get("internship")),
            is_ad=bool(raw.get("@isAdv")),
        )

    # ------------------------------------------------------------------ HTML

    def _parse_html_cards(self, soup: BeautifulSoup) -> PageResult:
        cards: list[Tag] = []
        for sel in ('[data-qa="vacancy-serp__vacancy"]', ".serp-item", '[data-qa="vacancy-preview"]'):
            cards = soup.select(sel)
            if cards:
                break
        if not cards:
            logger.warning("HH: карточки вакансий не найдены ни по одному селектору")
            return PageResult(vacancies=[])

        vacancies: list[VacancyData] = []
        for card in cards:
            link = card.select_one('[data-qa="serp-item__title"][href]') or card.select_one(".serp-item__title a")
            href = (link.get("href") or "") if link else ""
            match = _VACANCY_ID_RE.search(href)
            if not match:
                continue
            vacancy_id = match.group(1)

            title_el = card.select_one('[data-qa="serp-item__title-text"]') or link
            exp_el = card.select_one('[data-qa^="vacancy-serp__vacancy-work-experience"]')
            experience = None
            if exp_el is not None:
                experience = exp_el.get("data-qa", "").rsplit("-", 1)[-1] or None

            vacancies.append(VacancyData(
                id=vacancy_id,
                title=title_el.get_text(" ", strip=True) if title_el else "",
                url=f"https://hh.ru/vacancy/{vacancy_id}",
                employer=_text(card, '[data-qa="vacancy-serp__vacancy-employer-text"]'),
                salary=self._salary_from_html(card),
                experience=experience,
                work_formats=["REMOTE"] if card.select_one('[data-qa="vacancy-label-work-schedule-remote"]') else [],
                area=_text(card, '[data-qa="vacancy-serp__vacancy-address"]'),
            ))

        return PageResult(vacancies=vacancies)

    @staticmethod
    def _salary_from_html(card: Tag) -> Salary:
        amounts: list[int] = []
        currency = None
        for tag in card.select("data[value]"):
            value = tag.get("value", "")
            if value.isdigit():
                amounts.append(int(value))
            elif tag.get_text(strip=True) in _CURRENCY_SYMBOLS:
                currency = _CURRENCY_SYMBOLS[tag.get_text(strip=True)]
        return Salary(
            amount_from=amounts[0] if amounts else None,
            amount_to=amounts[1] if len(amounts) > 1 else None,
            currency=currency,
        )


def _text(card: Tag, selector: str) -> str | None:
    el = card.select_one(selector)
    text = el.get_text(" ", strip=True) if el else ""
    return text or None


def _to_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
