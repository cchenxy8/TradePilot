from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.enums import (
    BucketType,
    ComplianceStatus,
    RecommendationStatus,
    RecommendationType,
)
from backend.app.models.market_snapshot import MarketSnapshot
from backend.app.models.recommendation import Recommendation
from backend.app.models.watchlist import WatchlistItem
from backend.app.services.audit import log_event


def generate_swing_recommendations(db: Session) -> list[Recommendation]:
    watchlist_items = list(
        db.scalars(
            select(WatchlistItem)
            .where(WatchlistItem.bucket == BucketType.SWING, WatchlistItem.is_active.is_(True))
            .order_by(WatchlistItem.symbol.asc())
        )
    )

    created: list[Recommendation] = []
    for item in watchlist_items:
        snapshot = db.scalar(
            select(MarketSnapshot)
            .where(MarketSnapshot.watchlist_item_id == item.id)
            .order_by(MarketSnapshot.captured_at.desc())
            .limit(1)
        )
        if snapshot is None:
            continue

        above_ma = snapshot.mock_price > snapshot.moving_average_20
        rsi_in_range = 52 <= snapshot.rsi_14 <= 68
        positive_news = bool(snapshot.news_summary and "support" in snapshot.news_summary.lower())
        earnings_near = (
            snapshot.earnings_date is not None
            and 0 <= (snapshot.earnings_date - date.today()).days <= 14
        )
        existing_pending = db.scalar(
            select(Recommendation.id)
            .where(
                Recommendation.watchlist_item_id == item.id,
                Recommendation.status == RecommendationStatus.PENDING,
            )
            .limit(1)
        )
        if existing_pending is not None:
            continue
        if not (above_ma and rsi_in_range):
            continue

        confidence = round(
            0.5
            + (0.18 if above_ma else 0.0)
            + (0.14 if rsi_in_range else 0.0)
            + (0.08 if positive_news else 0.0)
            + (0.06 if earnings_near else 0.0),
            2,
        )
        recommendation = Recommendation(
            symbol=item.symbol,
            bucket=item.bucket,
            title=f"{item.symbol} swing candidate",
            rationale=item.thesis or "Swing candidate identified from watchlist and mock market data.",
            recommendation_type=(
                RecommendationType.SWING_ADD if earnings_near else RecommendationType.SWING_ENTRY
            ),
            why_now=(
                "Momentum is constructive with price above the 20-day moving average and RSI confirming trend quality."
            ),
            risk_notes=(
                "No automation is enabled. Manual review is required before any trade, especially if earnings are near."
            ),
            confidence_score=min(confidence, 0.96),
            compliance_status=ComplianceStatus.MANUAL_REVIEW_REQUIRED,
            source="swing_rule_engine",
            watchlist_item_id=item.id,
            market_snapshot_id=snapshot.id,
            mock_price=float(snapshot.mock_price),
            market_snapshot=snapshot.snapshot_payload,
        )
        db.add(recommendation)
        db.flush()
        log_event(
            db,
            event_type="recommendation.generated",
            entity_type="recommendation",
            entity_id=recommendation.id,
            payload={
                "symbol": recommendation.symbol,
                "recommendation_type": recommendation.recommendation_type.value,
                "confidence_score": recommendation.confidence_score,
                "compliance_status": recommendation.compliance_status.value,
                "engine": "swing_rule_engine",
            },
        )
        created.append(recommendation)

    db.commit()
    for recommendation in created:
        db.refresh(recommendation)
    return created
