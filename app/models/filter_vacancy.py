from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow
from app.db.types import UTCDateTime

# Статусы вакансии относительно фильтра
STATUS_SEEN = "seen"  # видели в обычном поиске или при первой проверке подписки — не присылать
STATUS_PENDING = "pending"  # нашла подписка, ждёт отправки (тихие часы, сбой отправки)
STATUS_NOTIFIED = "notified"  # отправлено уведомлением
STATUS_HIDDEN = "hidden"  # пользователь нажал «не интересно»


class FilterVacancy(Base):
    """Какие вакансии уже попадались по фильтру. Есть строка — вакансия не новая."""

    __tablename__ = "filter_vacancies"

    filter_id: Mapped[int] = mapped_column(ForeignKey("saved_filters.id", ondelete="CASCADE"), primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"), primary_key=True)

    status: Mapped[str] = mapped_column(String(16), default=STATUS_SEEN, server_default=STATUS_SEEN, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    notified_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
