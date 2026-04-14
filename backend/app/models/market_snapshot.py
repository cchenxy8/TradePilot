from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin


class MarketSnapshot(TimestampMixin, Base):
    __tablename__ = "market_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    watchlist_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("watchlist_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    latest_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    mock_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    volume: Mapped[int] = mapped_column(nullable=False)
    avg_volume_20d: Mapped[int] = mapped_column(nullable=False)
    moving_average_20: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    ma50: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    daily_change_pct: Mapped[float] = mapped_column(nullable=False)
    rsi_14: Mapped[float] = mapped_column(nullable=False)
    earnings_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    news_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
