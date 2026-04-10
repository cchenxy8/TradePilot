from datetime import datetime

from pydantic import BaseModel

from backend.app.models.enums import (
    BucketType,
    ComplianceStatus,
    RecommendationStatus,
    RecommendationType,
)
from backend.app.schemas.common import TimestampedRead


class RecommendationCreate(BaseModel):
    symbol: str
    bucket: BucketType
    title: str
    rationale: str
    recommendation_type: RecommendationType
    why_now: str
    risk_notes: str
    confidence_score: float
    compliance_status: ComplianceStatus = ComplianceStatus.MANUAL_REVIEW_REQUIRED
    source: str | None = None
    watchlist_item_id: int | None = None


class RecommendationRead(TimestampedRead):
    id: int
    symbol: str
    bucket: BucketType
    title: str
    rationale: str
    recommendation_type: RecommendationType
    why_now: str
    risk_notes: str
    confidence_score: float
    compliance_status: ComplianceStatus
    source: str | None
    status: RecommendationStatus
    watchlist_item_id: int | None
    market_snapshot_id: int | None
    mock_price: float | None
    market_snapshot: dict | None
    generated_at: datetime
    decided_at: datetime | None
    decision_reason: str | None
