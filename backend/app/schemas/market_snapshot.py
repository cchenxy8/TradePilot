from datetime import date, datetime

from backend.app.schemas.common import TimestampedRead


class MarketSnapshotRead(TimestampedRead):
    id: int
    symbol: str
    watchlist_item_id: int | None
    latest_price: float | None
    mock_price: float | None
    volume: int
    avg_volume_20d: int
    moving_average_20: float
    ma50: float
    daily_change_pct: float
    rsi_14: float
    earnings_date: date | None
    news_summary: str | None
    snapshot_payload: dict | None
    captured_at: datetime
