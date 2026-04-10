from sqlalchemy import Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin
from backend.app.models.enums import BucketType


class WatchlistItem(TimestampMixin, Base):
    __tablename__ = "watchlist_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    bucket: Mapped[BucketType] = mapped_column(Enum(BucketType), nullable=False, index=True)
    thesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
