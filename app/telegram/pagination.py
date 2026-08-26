from dataclasses import dataclass, field


@dataclass
class PaginationState:
    vacancies: list[dict] = field(default_factory=list)
    current_page: int = 0
    total: int = 0

    @property
    def pages(self) -> int:
        return max(1, (self.total + 2) // 3)

    @property
    def has_next(self) -> bool:
        return self.current_page < self.pages - 1

    @property
    def has_prev(self) -> bool:
        return self.current_page > 0

    def get_page_vacancies(self) -> list[dict]:
        start = self.current_page * 3
        end = start + 3
        return self.vacancies[start:end]

    def set_vacancies(self, vacancies: list[dict], total: int) -> None:
        self.vacancies = vacancies
        self.total = total
        self.current_page = 0

    def next_page(self) -> bool:
        if self.has_next:
            self.current_page += 1
            return True
        return False

    def prev_page(self) -> bool:
        if self.has_prev:
            self.current_page -= 1
            return True
        return False
