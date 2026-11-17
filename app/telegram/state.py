"""Состояние чата в памяти процесса.

Долговечное (сохранённые фильтры, вакансии) лежит в БД. Здесь — только то,
что нужно для текущего разговора: черновик фильтра в панели и последняя выдача.
После перезапуска бота черновик и выдача теряются, сохранённые фильтры — нет.
"""

from dataclasses import dataclass, field
from typing import Any

from app.services.filters import SearchFilters
from app.services.saved_filters import SavedFilterInfo
from app.services.search import SearchOutcome
from app.sniffers.schemas import VacancyData


@dataclass
class LoadedFilter:
    """Сохранённый фильтр, загруженный в панель."""

    id: int
    name: str
    params: dict[str, Any]  # как он лежит в БД — чтобы понять, менял ли его пользователь


@dataclass
class ChatSession:
    # Фильтры, которые пользователь сейчас настраивает
    filters: SearchFilters = field(default_factory=SearchFilters)
    loaded: LoadedFilter | None = None

    # Последняя выдача и с какими фильтрами она получена
    result: SearchOutcome | None = None
    result_filters: SearchFilters | None = None
    result_saved: LoadedFilter | None = None  # если искали по сохранённому фильтру без изменений
    page: int = 0
    page_size: int = 5
    results_message_id: int | None = None  # сообщение, в котором показана текущая выдача

    searching: bool = False

    # ---- сохранённый фильтр в панели

    def load(self, info: SavedFilterInfo) -> None:
        self.filters = info.filters.copy()
        self.loaded = LoadedFilter(info.id, info.name, info.filters.to_dict())

    def unload(self) -> None:
        self.loaded = None

    @property
    def loaded_is_modified(self) -> bool:
        return self.loaded is not None and self.filters.to_dict() != self.loaded.params

    def saved_for_search(self, filters: SearchFilters) -> LoadedFilter | None:
        """Сохранённый фильтр, к которому относится поиск (только если фильтр не меняли)."""
        if self.loaded is not None and filters.to_dict() == self.loaded.params:
            return self.loaded
        return None

    # ---- выдача

    @property
    def pages(self) -> int:
        if not self.result or not self.result.vacancies:
            return 1
        return (len(self.result.vacancies) + self.page_size - 1) // self.page_size

    def set_result(
        self, result: SearchOutcome, filters: SearchFilters, saved: LoadedFilter | None, message_id: int
    ) -> None:
        self.result = result
        self.result_filters = filters
        self.result_saved = saved
        self.results_message_id = message_id
        self.page = 0

    def set_page(self, page: int) -> None:
        self.page = max(0, min(page, self.pages - 1))

    def page_vacancies(self) -> list[VacancyData]:
        if not self.result:
            return []
        start = self.page * self.page_size
        return self.result.vacancies[start : start + self.page_size]


_sessions: dict[int, ChatSession] = {}


def get_session(chat_id: int, page_size: int = 5) -> ChatSession:
    session = _sessions.get(chat_id)
    if session is None:
        session = _sessions[chat_id] = ChatSession(page_size=page_size)
    return session
