from datetime import datetime

from pydantic import BaseModel

from backend.app.models.enums import BucketType, RecommendationStatus
from backend.app.schemas.common import TimestampedRead


class RecommendationCreate(BaseModel):
    symbol: str
    bucket: BucketType
    title: str
    rationale: str
    source: str | None = None
    watchlist_item_id: int | None = None


class RecommendationRead(TimestampedRead):
    id: int
    symbol: str
    bucket: BucketType
    title: str
    rationale: str
    source: str | None
    status: RecommendationStatus
    watchlist_item_id: int | None
    mock_price: float | None
    market_snapshot: dict | None
    generated_at: datetime
    decided_at: datetime | None
    decision_reason: str | None
