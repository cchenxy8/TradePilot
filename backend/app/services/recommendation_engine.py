from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.enums import (
    BucketType,
    ComplianceStatus,
    RecommendationAction,
    RecommendationDecisionStatus,
    SetupType,
)
from backend.app.models.recommendation import Recommendation
from backend.app.models.watchlist import WatchlistItem
from backend.app.services.audit import log_event
from backend.app.services.market_data import (
    get_active_snapshot_with_refresh_attempt,
    is_provider_backed,
    snapshot_price,
)


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
        snapshot = get_active_snapshot_with_refresh_attempt(db, item)
        if snapshot is None:
            continue

        price = snapshot_price(snapshot)
        above_ma = price > snapshot.moving_average_20
        rsi_in_range = 52 <= snapshot.rsi_14 <= 68
        positive_market_context = snapshot.daily_change_pct >= 0 and snapshot.volume >= snapshot.avg_volume_20d
        earnings_near = (
            snapshot.earnings_date is not None
            and 0 <= (snapshot.earnings_date - date.today()).days <= 14
        )
        existing_pending = db.scalar(
            select(Recommendation.id)
            .where(
                Recommendation.watchlist_item_id == item.id,
                Recommendation.decision_status == RecommendationDecisionStatus.PENDING,
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
            + (0.08 if positive_market_context else 0.0)
            + (0.06 if earnings_near else 0.0),
            2,
        )
        recommendation = Recommendation(
            symbol=item.symbol,
            bucket=item.bucket,
            title=f"{item.symbol} swing candidate",
            rationale=item.thesis or (
                "Swing candidate identified from watchlist and provider-backed market data."
                if is_provider_backed(snapshot)
                else "Swing candidate identified from watchlist and seeded fallback market data."
            ),
            recommendation_action=RecommendationAction.BUY,
            setup_type=SetupType.SWING_ADD if earnings_near else SetupType.SWING_ENTRY,
            why_now=(
                f"Latest price is above the 20-day moving average with RSI at {snapshot.rsi_14:.1f} "
                f"and daily change at {snapshot.daily_change_pct:.2f}%. "
                f"Active snapshot source is {snapshot.data_source_type} from {snapshot.data_provider}, "
                f"refreshed at {snapshot.refreshed_at.isoformat()}."
            ),
            risk_notes=(
                "No automation is enabled. Manual review is required before any trade, especially if earnings are near."
                + (
                    " This recommendation is using seeded fallback data because no provider-backed snapshot is available."
                    if not is_provider_backed(snapshot)
                    else ""
                )
            ),
            confidence_score=min(confidence, 0.96),
            compliance_status=ComplianceStatus.NEEDS_REVIEW,
            source="swing_rule_engine",
            watchlist_item_id=item.id,
            market_snapshot_id=snapshot.id,
            latest_price=float(price),
            mock_price=None,
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
                "recommendation_action": recommendation.recommendation_action.value,
                "setup_type": recommendation.setup_type.value,
                "confidence_score": recommendation.confidence_score,
                "compliance_status": recommendation.compliance_status.value,
                "market_snapshot_id": snapshot.id,
                "data_provider": snapshot.data_provider,
                "data_source_type": snapshot.data_source_type,
                "refreshed_at": snapshot.refreshed_at.isoformat(),
                "is_provider_backed": is_provider_backed(snapshot),
                "engine": "swing_rule_engine",
            },
        )
        created.append(recommendation)

    db.commit()
    for recommendation in created:
        db.refresh(recommendation)
    return created
