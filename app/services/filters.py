"""Пользовательский фильтр поиска.

Фильтр = общая часть (текст, опыт, занятость, «только с ЗП») + список локаций.
Каждая локация — пара «регион + форматы работы», выдача — ОБЪЕДИНЕНИЕ локаций:

    Россия · Удалённо           ─┐
                                 ├─> одна выдача без повторов
    Краснодар · Офис, Гибрид    ─┘

HH так одним запросом не умеет (параметры area и work_format у него
соединяются через «И»), поэтому на каждую локацию делается свой запрос.

Фильтр сериализуется в dict (to_dict/from_dict) — в таком виде он будет
храниться в БД для сохранённых фильтров и подписок.
"""

from dataclasses import dataclass, field
from typing import Any

from app.sniffers.hh.query import EmploymentForm, Experience, HHQuery, Label, OrderBy, WorkFormat

# Регионы HH, которые можно выбрать кнопками (area id). None — без ограничения.
AREAS: dict[int | None, str] = {
    113: "Россия",
    1: "Москва",
    2: "Санкт-Петербург",
    53: "Краснодар",
    None: "Везде",
}
RUSSIA_AREA_ID = 113
MAX_LOCATIONS = 4

_WORK_FORMAT_ORDER = [WorkFormat.REMOTE, WorkFormat.HYBRID, WorkFormat.ON_SITE, WorkFormat.FIELD_WORK]


def area_name(area_id: int | None) -> str:
    return AREAS.get(area_id, f"Регион {area_id}")


def _sorted(values: set) -> tuple:
    # стабильный порядок -> стабильный URL и сериализация
    return tuple(sorted(values, key=lambda v: v.value))


@dataclass
class LocationRule:
    area_id: int | None = RUSSIA_AREA_ID
    work_formats: set[WorkFormat] = field(default_factory=set)  # пусто — любой формат

    @property
    def area_name(self) -> str:
        return area_name(self.area_id)

    def copy(self) -> "LocationRule":
        return LocationRule(area_id=self.area_id, work_formats=set(self.work_formats))

    def to_dict(self) -> dict[str, Any]:
        return {"area_id": self.area_id, "work_formats": [f.value for f in _sorted(self.work_formats)]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LocationRule":
        return cls(
            area_id=data.get("area_id"),
            work_formats={WorkFormat(v) for v in data.get("work_formats") or []},
        )

    def ordered_work_formats(self) -> list[WorkFormat]:
        return [f for f in _WORK_FORMAT_ORDER if f in self.work_formats]


@dataclass
class SearchFilters:
    text: str = ""
    employment_forms: set[EmploymentForm] = field(default_factory=set)
    experiences: set[Experience] = field(default_factory=set)
    only_with_salary: bool = False
    locations: list[LocationRule] = field(default_factory=lambda: [LocationRule()])

    def copy(self) -> "SearchFilters":
        return SearchFilters.from_dict(self.to_dict())

    # ---- локации

    def add_location(self, rule: LocationRule | None = None) -> int | None:
        """Добавляет локацию и возвращает её индекс (None — достигнут лимит)."""
        if len(self.locations) >= MAX_LOCATIONS:
            return None
        self.locations.append(rule or LocationRule())
        return len(self.locations) - 1

    def remove_location(self, index: int) -> None:
        if len(self.locations) > 1 and 0 <= index < len(self.locations):
            self.locations.pop(index)

    def apply_remote_plus_home(self, home_area_id: int) -> None:
        """Шаблон «удалёнка откуда угодно + мой город в офисе/гибриде».

        Удалёнку из своего города покрывает первая локация (Россия включает
        все города), поэтому во второй только офис и гибрид — так счётчики
        и метки на карточках не дублируются.
        """
        self.locations = [
            LocationRule(area_id=RUSSIA_AREA_ID, work_formats={WorkFormat.REMOTE}),
            LocationRule(area_id=home_area_id, work_formats={WorkFormat.ON_SITE, WorkFormat.HYBRID}),
        ]

    # ---- запросы к HH

    def to_hh_queries(self) -> list[HHQuery]:
        """Один HHQuery на каждую локацию, в том же порядке, что и self.locations."""
        common = dict(
            text=self.text.strip() or None,
            employment_form=_sorted(self.employment_forms),
            experience=_sorted(self.experiences),
            label=(Label.with_salary,) if self.only_with_salary else (),
            # при объединении нескольких выдач честно сравнивать можно только по дате
            order_by=OrderBy.PUBLICATION_TIME if len(self.locations) > 1 else None,
        )
        return [
            HHQuery(area=rule.area_id, work_format=_sorted(rule.work_formats), **common)
            for rule in self.locations
        ]

    # ---- сериализация (для БД / подписок)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "employment_forms": [e.value for e in _sorted(self.employment_forms)],
            "experiences": [e.value for e in _sorted(self.experiences)],
            "only_with_salary": self.only_with_salary,
            "locations": [rule.to_dict() for rule in self.locations],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SearchFilters":
        locations = [LocationRule.from_dict(r) for r in data.get("locations") or []]
        return cls(
            text=data.get("text") or "",
            employment_forms={EmploymentForm(v) for v in data.get("employment_forms") or []},
            experiences={Experience(v) for v in data.get("experiences") or []},
            only_with_salary=bool(data.get("only_with_salary")),
            locations=locations or [LocationRule()],
        )
