"""Состояние чата в памяти процесса.

Пока без БД: после перезапуска бота фильтры и последняя выдача теряются.
Когда появятся модели Subscription/Vacancy, это место заменится репозиторием.
"""

from dataclasses import dataclass, field

from app.services.search import SearchFilters
from app.sniffers.schemas import SearchResult, VacancyData


@dataclass
class ChatSession:
    # Фильтры, которые пользователь сейчас настраивает
    filters: SearchFilters = field(default_factory=SearchFilters)

    # Последняя выдача и фильтры, с которыми она была получена
    result: SearchResult | None = None
    result_filters: SearchFilters | None = None
    page: int = 0
    page_size: int = 5
    results_message_id: int | None = None  # сообщение, в котором показана текущая выдача

    searching: bool = False

    @property
    def pages(self) -> int:
        if not self.result or not self.result.vacancies:
            return 1
        return (len(self.result.vacancies) + self.page_size - 1) // self.page_size

    def set_result(self, result: SearchResult, filters: SearchFilters, message_id: int) -> None:
        self.result = result
        self.result_filters = filters
        self.results_message_id = message_id
        self.page = 0

    def set_page(self, page: int) -> None:
        self.page = max(0, min(page, self.pages - 1))

    def page_vacancies(self) -> list[VacancyData]:
        if not self.result:
            return []
        start = self.page * self.page_size
        return self.result.vacancies[start:start + self.page_size]


_sessions: dict[int, ChatSession] = {}


def get_session(chat_id: int, page_size: int = 5) -> ChatSession:
    session = _sessions.get(chat_id)
    if session is None:
        session = _sessions[chat_id] = ChatSession(page_size=page_size)
    return session
