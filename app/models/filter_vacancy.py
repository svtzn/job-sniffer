from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow
from app.db.types import UTCDateTime


class FilterVacancy(Base):
    """Какие вакансии уже попадались по фильтру.

    Строка есть  -> вакансия «уже видена», подписка её не пришлёт.
    notified_at  -> когда отправили уведомлением (None — видели в обычном поиске).
    hidden       -> пользователь нажал «не интересно».
    """

    __tablename__ = "filter_vacancies"

    filter_id: Mapped[int] = mapped_column(ForeignKey("saved_filters.id", ondelete="CASCADE"), primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"), primary_key=True)

    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    notified_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    hidden: Mapped[bool] = mapped_column(default=False)
