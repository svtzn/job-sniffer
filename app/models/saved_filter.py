from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow
from app.db.types import UTCDateTime


class SavedFilter(Base):
    """Сохранённый фильтр пользователя. Подписка — это тот же фильтр с is_subscribed=True."""

    __tablename__ = "saved_filters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)  # куда слать уведомления
    name: Mapped[str] = mapped_column(String(100))
    params: Mapped[dict[str, Any]] = mapped_column(JSON)  # SearchFilters.to_dict()

    is_subscribed: Mapped[bool] = mapped_column(default=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
