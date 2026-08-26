from datetime import datetime, timezone

from sqlalchemy import Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    search_url: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(server_default=func.true())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    last_checked_at: Mapped[datetime | None] = mapped_column(nullable=True)
