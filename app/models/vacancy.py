from datetime import datetime

from sqlalchemy import JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow
from app.db.types import UTCDateTime


class Vacancy(Base):
    """Нормализованная вакансия из любого источника. Одна строка на (source, external_id)."""

    __tablename__ = "vacancies"
    __table_args__ = (UniqueConstraint("source", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50))
    external_id: Mapped[str] = mapped_column(String(64))

    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(1000))

    employer: Mapped[str | None] = mapped_column(String(500))
    employer_trusted: Mapped[bool] = mapped_column(default=False)
    employer_rating: Mapped[float | None]

    salary_from: Mapped[int | None]
    salary_to: Mapped[int | None]
    salary_currency: Mapped[str | None] = mapped_column(String(10))
    salary_gross: Mapped[bool | None]
    salary_mode: Mapped[str | None] = mapped_column(String(32))

    experience: Mapped[str | None] = mapped_column(String(32))
    work_formats: Mapped[list[str]] = mapped_column(JSON, default=list)
    employment_form: Mapped[str | None] = mapped_column(String(32))
    area: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(1000))
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    responses_count: Mapped[int | None]
    is_internship: Mapped[bool] = mapped_column(default=False)

    # Полное описание со страницы вакансии — заполнится, когда начнём его загружать (для матчера/ИИ)
    description: Mapped[str | None] = mapped_column(Text)

    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
