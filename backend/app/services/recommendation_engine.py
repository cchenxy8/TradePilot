from datetime import date, datetime
from decimal import Decimal

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


def _pct_distance(value: Decimal, reference: Decimal) -> float:
    if reference == 0:
        return 0.0
    return float(((value - reference) / reference) * 100)


def _evaluate_swing_rules(snapshot, price: Decimal) -> dict:
    days_to_earnings = (
        (snapshot.earnings_date - date.today()).days
        if snapshot.earnings_date is not None
        else None
    )
    price_above_ma20_pct = _pct_distance(price, snapshot.moving_average_20)
    ma20_above_ma50_pct = _pct_distance(snapshot.moving_average_20, snapshot.ma50)
    volume_ratio = snapshot.volume / snapshot.avg_volume_20d if snapshot.avg_volume_20d else 0.0

    passed_signals: list[str] = []
    failed_signals: list[str] = []
    penalties: list[str] = []
    score = 0.32

    if price_above_ma20_pct >= 0:
        contribution = min(0.2, 0.1 + (price_above_ma20_pct / 100))
        score += contribution
        passed_signals.append(
            f"Price is {price_above_ma20_pct:.1f}% above the 20-day moving average."
        )
    else:
        score -= 0.18
        failed_signals.append("Price is not above the 20-day moving average.")
        penalties.append(f"Price is {abs(price_above_ma20_pct):.1f}% below the 20-day moving average.")

    if ma20_above_ma50_pct >= 0:
        contribution = min(0.16, 0.08 + (ma20_above_ma50_pct / 120))
        score += contribution
        passed_signals.append(
            f"The 20-day moving average is {ma20_above_ma50_pct:.1f}% above the 50-day moving average."
        )
    else:
        score -= 0.12
        failed_signals.append("The 20-day moving average is not above the 50-day moving average.")
        penalties.append(f"The 20-day moving average is {abs(ma20_above_ma50_pct):.1f}% below the 50-day moving average.")

    if 52 <= snapshot.rsi_14 <= 68:
        distance_from_center = abs(snapshot.rsi_14 - 60)
        contribution = max(0.08, 0.16 - (distance_from_center * 0.01))
        score += contribution
        passed_signals.append(f"RSI is {snapshot.rsi_14:.1f}, inside the preferred swing range.")
    elif 45 <= snapshot.rsi_14 < 52:
        score += 0.04
        failed_signals.append("RSI is below the preferred 52-68 swing range.")
        penalties.append(f"RSI is {snapshot.rsi_14:.1f}, constructive but not yet in the preferred range.")
    elif 68 < snapshot.rsi_14 <= 75:
        score -= 0.03 + min(0.07, (snapshot.rsi_14 - 68) * 0.01)
        failed_signals.append("RSI is above the preferred 52-68 swing range.")
        penalties.append(f"RSI is {snapshot.rsi_14:.1f}, which may be extended for a fresh entry.")
    else:
        score -= 0.16
        failed_signals.append("RSI is outside the acceptable swing range.")
        penalties.append(f"RSI is {snapshot.rsi_14:.1f}, outside the preferred swing range.")

    if volume_ratio >= 1.15:
        score += min(0.12, 0.06 + ((volume_ratio - 1.15) * 0.08))
        passed_signals.append(f"Volume is {volume_ratio:.2f}x the 20-day average.")
    elif volume_ratio >= 0.85:
        score += max(0.0, (volume_ratio - 0.85) * 0.08)
        failed_signals.append("Volume is not meaningfully above the 20-day average.")
        penalties.append(f"Volume confirmation is modest at {volume_ratio:.2f}x the 20-day average.")
    else:
        score -= 0.08
        failed_signals.append("Volume is below the 20-day average.")
        penalties.append(f"Volume is light at {volume_ratio:.2f}x the 20-day average.")

    if snapshot.daily_change_pct >= 0:
        score += min(0.06, snapshot.daily_change_pct * 0.015)
        passed_signals.append(f"Daily change is positive at {snapshot.daily_change_pct:.2f}%.")
    else:
        score -= min(0.08, abs(snapshot.daily_change_pct) * 0.02)
        failed_signals.append("Daily change is negative.")
        penalties.append(f"Daily change is negative at {snapshot.daily_change_pct:.2f}%.")

    if days_to_earnings is not None and 0 <= days_to_earnings <= 7:
        score -= 0.12
        failed_signals.append("Earnings are inside the high-risk seven-day window.")
        penalties.append(f"Earnings are in {days_to_earnings} days, adding gap risk.")
    elif days_to_earnings is not None and 8 <= days_to_earnings <= 14:
        score -= 0.05
        failed_signals.append("Earnings are close enough to affect swing risk.")
        penalties.append(f"Earnings are in {days_to_earnings} days, so position sizing needs extra care.")
    elif days_to_earnings is not None:
        passed_signals.append(f"Earnings are {days_to_earnings} days away.")

    required = price_above_ma20_pct >= 0 and ma20_above_ma50_pct >= 0 and 48 <= snapshot.rsi_14 <= 75
    score = min(max(round(score, 2), 0.05), 0.92)
    return {
        "confidence": score,
        "passed_signals": passed_signals,
        "failed_signals": failed_signals,
        "penalties": penalties,
        "required": required,
        "days_to_earnings": days_to_earnings,
        "volume_ratio": volume_ratio,
        "price_above_ma20_pct": price_above_ma20_pct,
        "ma20_above_ma50_pct": ma20_above_ma50_pct,
        "final_score": score,
    }


def _join_rules(items: list[str], fallback: str) -> str:
    return " ".join(items) if items else fallback


def _recommendation_action(evaluation: dict) -> RecommendationAction:
    if evaluation["required"] and evaluation["confidence"] >= 0.52:
        return RecommendationAction.BUY
    if evaluation["confidence"] >= 0.35:
        return RecommendationAction.WATCH
    return RecommendationAction.AVOID


def _recommendation_title(symbol: str, action: RecommendationAction) -> str:
    if action == RecommendationAction.BUY:
        return f"{symbol} swing candidate"
    if action == RecommendationAction.WATCH:
        return f"{symbol} swing watch"
    return f"{symbol} swing risk review"


def generate_swing_recommendations(db: Session) -> list[Recommendation]:
    watchlist_items = list(
        db.scalars(
            select(WatchlistItem)
            .where(WatchlistItem.bucket == BucketType.SWING, WatchlistItem.is_active.is_(True))
            .order_by(WatchlistItem.symbol.asc())
        )
    )

    recommendations: list[Recommendation] = []
    for item in watchlist_items:
        snapshot = get_active_snapshot_with_refresh_attempt(db, item)
        if snapshot is None:
            continue

        price = snapshot_price(snapshot)
        evaluation = _evaluate_swing_rules(snapshot, price)
        days_to_earnings = evaluation["days_to_earnings"]
        earnings_near = days_to_earnings is not None and 0 <= days_to_earnings <= 14
        existing_pending = db.scalar(
            select(Recommendation)
            .where(
                Recommendation.watchlist_item_id == item.id,
                Recommendation.decision_status == RecommendationDecisionStatus.PENDING,
            )
            .limit(1)
        )
        action = _recommendation_action(evaluation)
        if existing_pending is None and action != RecommendationAction.BUY:
            continue

        source_note = (
            "Provider-backed delayed market snapshot."
            if is_provider_backed(snapshot)
            else "Seeded fallback market snapshot; provider-backed data was unavailable."
        )
        signal_text = _join_rules(evaluation["passed_signals"], "No positive swing signals passed.")
        penalty_text = _join_rules(evaluation["penalties"], "No major rule penalties were detected.")
        failed_text = _join_rules(evaluation["failed_signals"], "No core swing checks failed.")
        rule_results = {
            "passed_signals": evaluation["passed_signals"],
            "failed_signals": evaluation["failed_signals"],
            "penalties": evaluation["penalties"],
            "final_score": evaluation["final_score"],
            "required_rules_passed": evaluation["required"],
            "metrics": {
                "price_above_ma20_pct": round(evaluation["price_above_ma20_pct"], 2),
                "ma20_above_ma50_pct": round(evaluation["ma20_above_ma50_pct"], 2),
                "volume_ratio": round(evaluation["volume_ratio"], 2),
                "rsi_14": snapshot.rsi_14,
                "daily_change_pct": snapshot.daily_change_pct,
                "days_to_earnings": days_to_earnings,
            },
        }
        recommendation_fields = {
            "symbol": item.symbol,
            "bucket": item.bucket,
            "title": _recommendation_title(item.symbol, action),
            "rationale": (
                f"{item.thesis + ' ' if item.thesis else ''}"
                f"Passed rules: {signal_text} Confidence was reduced by: {penalty_text} {source_note}"
            ),
            "recommendation_action": action,
            "setup_type": (
                SetupType.SWING_ADD
                if earnings_near and action != RecommendationAction.AVOID
                else SetupType.SWING_ENTRY
            ),
            "why_now": (
                f"{signal_text} "
                f"Active snapshot source is {snapshot.data_source_type} from {snapshot.data_provider}, "
                f"refreshed at {snapshot.refreshed_at.isoformat()}."
            ),
            "risk_notes": (
                f"{penalty_text} Failed checks: {failed_text} "
                "No automation is enabled. Manual review is required before any trade."
                + (
                    " This recommendation is using seeded fallback data because no provider-backed snapshot is available."
                    if not is_provider_backed(snapshot)
                    else ""
                )
            ),
            "confidence_score": evaluation["confidence"],
            "compliance_status": ComplianceStatus.NEEDS_REVIEW,
            "source": "swing_rule_engine",
            "watchlist_item_id": item.id,
            "market_snapshot_id": snapshot.id,
            "latest_price": float(price),
            "mock_price": None,
            "market_snapshot": snapshot.snapshot_payload,
            "rule_results": rule_results,
            "generated_at": datetime.utcnow(),
        }
        if existing_pending is not None:
            recommendation = existing_pending
            for field, value in recommendation_fields.items():
                setattr(recommendation, field, value)
            event_type = "recommendation.refreshed_by_rules"
        else:
            recommendation = Recommendation(**recommendation_fields)
            db.add(recommendation)
            event_type = "recommendation.generated"
        db.flush()
        log_event(
            db,
            event_type=event_type,
            entity_type="recommendation",
            entity_id=recommendation.id,
            payload={
                "symbol": recommendation.symbol,
                "recommendation_action": recommendation.recommendation_action.value,
                "setup_type": recommendation.setup_type.value,
                "confidence_score": recommendation.confidence_score,
                "passed_signals": evaluation["passed_signals"],
                "failed_signals": evaluation["failed_signals"],
                "penalties": evaluation["penalties"],
                "final_score": evaluation["final_score"],
                "rule_metrics": {
                    "price_above_ma20_pct": round(evaluation["price_above_ma20_pct"], 2),
                    "ma20_above_ma50_pct": round(evaluation["ma20_above_ma50_pct"], 2),
                    "volume_ratio": round(evaluation["volume_ratio"], 2),
                    "days_to_earnings": days_to_earnings,
                },
                "compliance_status": recommendation.compliance_status.value,
                "market_snapshot_id": snapshot.id,
                "data_provider": snapshot.data_provider,
                "data_source_type": snapshot.data_source_type,
                "refreshed_at": snapshot.refreshed_at.isoformat(),
                "is_provider_backed": is_provider_backed(snapshot),
                "engine": "swing_rule_engine",
            },
        )
        recommendations.append(recommendation)

    db.commit()
    for recommendation in recommendations:
        db.refresh(recommendation)
    return recommendations
