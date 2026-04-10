from datetime import date, datetime

from backend.app.schemas.common import TimestampedRead


class MarketSnapshotRead(TimestampedRead):
    id: int
    symbol: str
    watchlist_item_id: int | None
    mock_price: float
    volume: int
    moving_average_20: float
    rsi_14: float
    earnings_date: date | None
    news_summary: str | None
    snapshot_payload: dict | None
    captured_at: datetime
