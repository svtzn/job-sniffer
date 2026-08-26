from datetime import datetime, timezone

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Vacancy(Base):
    __tablename__ = "vacancies"

    id: Mapped[str] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(50), default="hh_ru")
    first_seen_at: Mapped[datetime] = mapped_column(default=_utcnow)
