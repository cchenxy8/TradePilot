from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

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
from backend.app.services.swing_scoring_config import (
    SWING_RULE_BOUNDS,
    SWING_SCORE_BASE,
    SWING_SCORE_BONUSES,
    SWING_SCORE_LIMITS,
    SWING_SCORE_PENALTIES,
    SWING_SCORE_THRESHOLDS,
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
    constructive_trend = price_above_ma20_pct >= 0 and ma20_above_ma50_pct >= 0

    passed_signals: list[str] = []
    failed_signals: list[str] = []
    penalties: list[str] = []
    avoid_reasons: list[str] = []
    score = SWING_SCORE_BASE

    if 0 <= price_above_ma20_pct <= SWING_RULE_BOUNDS["price_extended_above_ma20_pct"]:
        score += SWING_SCORE_BONUSES["price_above_ma20"]
        passed_signals.append(
            f"Price is {price_above_ma20_pct:.1f}% above the 20-day moving average."
        )
    elif price_above_ma20_pct > SWING_RULE_BOUNDS["price_extended_above_ma20_pct"]:
        score += SWING_SCORE_BONUSES["price_above_ma20_extended"]
        passed_signals.append("Price is above the 20-day moving average.")
        penalties.append(
            f"Price is {price_above_ma20_pct:.1f}% above the 20-day moving average, which is extended for a fresh swing entry."
        )
    else:
        penalty = (
            SWING_SCORE_PENALTIES["price_slightly_below_ma20"]
            if price_above_ma20_pct >= SWING_RULE_BOUNDS["price_materially_below_ma20_pct"]
            else SWING_SCORE_PENALTIES["price_materially_below_ma20"]
        )
        score -= penalty
        failed_signals.append("Price is not above the 20-day moving average.")
        penalties.append(f"Price is {abs(price_above_ma20_pct):.1f}% below the 20-day moving average.")
        if price_above_ma20_pct < SWING_RULE_BOUNDS["price_materially_below_ma20_pct"]:
            avoid_reasons.append("Price is materially below the 20-day moving average.")

    if ma20_above_ma50_pct >= SWING_RULE_BOUNDS["ma20_meaningfully_above_ma50_pct"]:
        score += SWING_SCORE_BONUSES["ma20_above_ma50"]
        passed_signals.append(
            f"The 20-day moving average is {ma20_above_ma50_pct:.1f}% above the 50-day moving average."
        )
    elif ma20_above_ma50_pct >= 0:
        score += SWING_SCORE_BONUSES["ma20_slightly_above_ma50"]
        passed_signals.append("The 20-day moving average is slightly above the 50-day moving average.")
    else:
        score -= SWING_SCORE_PENALTIES["ma20_below_ma50"]
        failed_signals.append("The 20-day moving average is not above the 50-day moving average.")
        penalties.append(f"The 20-day moving average is {abs(ma20_above_ma50_pct):.1f}% below the 50-day moving average.")
        avoid_reasons.append("Short-term trend is below the 50-day trend.")

    if SWING_RULE_BOUNDS["rsi_preferred_min"] <= snapshot.rsi_14 <= SWING_RULE_BOUNDS["rsi_preferred_max"]:
        distance_from_center = abs(snapshot.rsi_14 - 60)
        contribution = max(
            SWING_SCORE_BONUSES["rsi_preferred_min"],
            SWING_SCORE_BONUSES["rsi_preferred_max"] - (distance_from_center * 0.008),
        )
        score += contribution
        passed_signals.append(f"RSI is {snapshot.rsi_14:.1f}, inside the preferred swing range.")
        rsi_zone = "preferred"
    elif SWING_RULE_BOUNDS["rsi_preferred_max"] < snapshot.rsi_14 <= SWING_RULE_BOUNDS["rsi_slightly_extended_max"]:
        score -= SWING_SCORE_PENALTIES["rsi_slightly_extended"]
        failed_signals.append("RSI is slightly extended above the preferred swing range.")
        penalties.append(f"RSI is {snapshot.rsi_14:.1f}, so reward-to-risk may be less favorable.")
        rsi_zone = "slightly_extended"
    elif SWING_RULE_BOUNDS["rsi_slightly_extended_max"] < snapshot.rsi_14 <= SWING_RULE_BOUNDS["rsi_extended_max"]:
        score -= SWING_SCORE_PENALTIES["rsi_extended"]
        failed_signals.append("RSI is extended.")
        penalties.append(f"RSI is {snapshot.rsi_14:.1f}, which is extended for a new swing entry.")
        rsi_zone = "extended"
    elif snapshot.rsi_14 > SWING_RULE_BOUNDS["rsi_extended_max"]:
        score -= SWING_SCORE_PENALTIES["rsi_overheated"]
        failed_signals.append("RSI is overheated.")
        penalties.append(f"RSI is {snapshot.rsi_14:.1f}, an overheated reading for this swing model.")
        if not constructive_trend or snapshot.rsi_14 >= SWING_RULE_BOUNDS["rsi_auto_avoid_min"]:
            avoid_reasons.append("RSI is overheated.")
        rsi_zone = "overheated"
    elif SWING_RULE_BOUNDS["rsi_soft_min"] <= snapshot.rsi_14 < SWING_RULE_BOUNDS["rsi_preferred_min"]:
        score -= SWING_SCORE_PENALTIES["rsi_soft"]
        failed_signals.append("RSI is below the preferred swing range.")
        penalties.append(f"RSI is {snapshot.rsi_14:.1f}, which suggests momentum is not confirmed yet.")
        rsi_zone = "soft"
    else:
        score -= SWING_SCORE_PENALTIES["rsi_weak"]
        failed_signals.append("RSI is outside the acceptable swing range.")
        penalties.append(f"RSI is {snapshot.rsi_14:.1f}, outside the preferred swing range.")
        avoid_reasons.append("RSI is too weak for the swing model.")
        rsi_zone = "weak"

    if volume_ratio >= SWING_RULE_BOUNDS["volume_confirmed_ratio"]:
        score += min(
            SWING_SCORE_BONUSES["volume_above_average_max"],
            SWING_SCORE_BONUSES["volume_above_average_base"]
            + ((volume_ratio - SWING_RULE_BOUNDS["volume_confirmed_ratio"]) * 0.04),
        )
        passed_signals.append(f"Volume is {volume_ratio:.2f}x the 20-day average.")
    elif volume_ratio >= SWING_RULE_BOUNDS["volume_near_confirmed_ratio"]:
        score += SWING_SCORE_BONUSES["volume_near_confirmation"]
        passed_signals.append(f"Volume is near confirmation at {volume_ratio:.2f}x the 20-day average.")
    elif volume_ratio >= SWING_RULE_BOUNDS["volume_weak_ratio"]:
        score -= SWING_SCORE_PENALTIES["volume_weak"]
        failed_signals.append("Volume is not meaningfully above the 20-day average.")
        penalties.append(f"Volume confirmation is weak at {volume_ratio:.2f}x the 20-day average.")
    else:
        score -= SWING_SCORE_PENALTIES["volume_light"]
        failed_signals.append("Volume is below the 20-day average.")
        penalties.append(f"Volume is light at {volume_ratio:.2f}x the 20-day average.")
        if not constructive_trend or volume_ratio < SWING_RULE_BOUNDS["volume_extremely_weak_ratio"]:
            avoid_reasons.append("Volume is too light to confirm the setup.")

    if (
        SWING_RULE_BOUNDS["daily_change_constructive_min_pct"]
        <= snapshot.daily_change_pct
        <= SWING_RULE_BOUNDS["daily_change_constructive_max_pct"]
    ):
        score += SWING_SCORE_BONUSES["daily_change_constructive"]
        passed_signals.append(f"Daily change is constructive at {snapshot.daily_change_pct:.2f}%.")
    elif 0 <= snapshot.daily_change_pct < SWING_RULE_BOUNDS["daily_change_constructive_min_pct"]:
        score += SWING_SCORE_BONUSES["daily_change_slightly_positive"]
        passed_signals.append(f"Daily change is slightly positive at {snapshot.daily_change_pct:.2f}%.")
    elif snapshot.daily_change_pct > SWING_RULE_BOUNDS["daily_change_constructive_max_pct"]:
        score -= SWING_SCORE_PENALTIES["daily_change_stretched"]
        failed_signals.append("Daily move is stretched.")
        penalties.append(f"Daily change is +{snapshot.daily_change_pct:.2f}%, which may be chasing strength.")
    else:
        score -= min(
            SWING_SCORE_PENALTIES["daily_change_negative_max"],
            SWING_SCORE_PENALTIES["daily_change_negative_base"]
            + abs(snapshot.daily_change_pct) * 0.025,
        )
        failed_signals.append("Daily change is negative.")
        penalties.append(f"Daily change is negative at {snapshot.daily_change_pct:.2f}%.")

    if days_to_earnings is not None and 0 <= days_to_earnings <= SWING_RULE_BOUNDS["earnings_high_risk_days"]:
        score -= SWING_SCORE_PENALTIES["earnings_within_7_days"]
        failed_signals.append("Earnings are inside the high-risk seven-day window.")
        penalties.append(f"Earnings are in {days_to_earnings} days, adding gap risk.")
        avoid_reasons.append("Earnings are too close for a clean swing setup.")
    elif (
        days_to_earnings is not None
        and SWING_RULE_BOUNDS["earnings_high_risk_days"] < days_to_earnings <= SWING_RULE_BOUNDS["earnings_caution_days"]
    ):
        score -= SWING_SCORE_PENALTIES["earnings_within_14_days"]
        failed_signals.append("Earnings are close enough to affect swing risk.")
        penalties.append(f"Earnings are in {days_to_earnings} days, so position sizing needs extra care.")
    elif days_to_earnings is not None:
        passed_signals.append(f"Earnings are {days_to_earnings} days away.")

    required = (
        constructive_trend
        and SWING_RULE_BOUNDS["rsi_preferred_min"] <= snapshot.rsi_14 <= SWING_RULE_BOUNDS["rsi_slightly_extended_max"]
        and len(avoid_reasons) == 0
    )
    score = min(max(round(score, 2), SWING_SCORE_LIMITS["min"]), SWING_SCORE_LIMITS["max"])
    return {
        "confidence": score,
        "passed_signals": passed_signals,
        "failed_signals": failed_signals,
        "penalties": penalties,
        "avoid_reasons": avoid_reasons,
        "required": required,
        "days_to_earnings": days_to_earnings,
        "volume_ratio": volume_ratio,
        "price_above_ma20_pct": price_above_ma20_pct,
        "ma20_above_ma50_pct": ma20_above_ma50_pct,
        "rsi_zone": rsi_zone,
        "constructive_trend": constructive_trend,
        "final_score": score,
    }


def _join_rules(items: list[str], fallback: str) -> str:
    return " ".join(items) if items else fallback


def _recommendation_action(evaluation: dict) -> RecommendationAction:
    has_avoid_pressure = len(evaluation["avoid_reasons"]) > 0
    has_too_many_penalties = len(evaluation["penalties"]) > SWING_RULE_BOUNDS["maximum_buy_penalties"]
    enough_positive_signals = len(evaluation["passed_signals"]) >= SWING_RULE_BOUNDS["minimum_buy_signals"]

    if evaluation["confidence"] <= SWING_SCORE_THRESHOLDS["avoid"]:
        return RecommendationAction.AVOID
    if (
        evaluation["confidence"] >= SWING_SCORE_THRESHOLDS["buy"]
        and evaluation["required"]
        and enough_positive_signals
        and not has_avoid_pressure
        and not has_too_many_penalties
    ):
        return RecommendationAction.BUY
    if (
        SWING_SCORE_THRESHOLDS["watch"] <= evaluation["confidence"] < SWING_SCORE_THRESHOLDS["buy"]
        and not has_avoid_pressure
    ):
        return RecommendationAction.WATCH
    if evaluation["constructive_trend"] and not has_avoid_pressure:
        return RecommendationAction.WATCH
    return RecommendationAction.AVOID


def _recommendation_title(symbol: str, action: RecommendationAction) -> str:
    if action == RecommendationAction.BUY:
        return f"{symbol} swing candidate"
    if action == RecommendationAction.WATCH:
        return f"{symbol} swing watch"
    return f"{symbol} swing risk review"


def swing_calibration_examples() -> list[dict]:
    examples = [
        {
            "setup_type": "mild_constructive",
            "description": "Constructive trend, preferred RSI, confirmed volume.",
            "price": Decimal("104"),
            "snapshot": SimpleNamespace(
                moving_average_20=Decimal("100"),
                ma50=Decimal("96"),
                rsi_14=58.0,
                volume=1_450_000,
                avg_volume_20d=1_000_000,
                daily_change_pct=1.2,
                earnings_date=date.today() + timedelta(days=35),
            ),
        },
        {
            "setup_type": "mixed_constructive",
            "description": "Trend is positive, but volume is only modest and RSI is slightly extended.",
            "price": Decimal("104"),
            "snapshot": SimpleNamespace(
                moving_average_20=Decimal("100"),
                ma50=Decimal("96"),
                rsi_14=67.0,
                volume=820_000,
                avg_volume_20d=1_000_000,
                daily_change_pct=1.2,
                earnings_date=date.today() + timedelta(days=35),
            ),
        },
        {
            "setup_type": "extended_constructive",
            "description": "Trend is positive, but RSI is extended and volume is below average.",
            "price": Decimal("104"),
            "snapshot": SimpleNamespace(
                moving_average_20=Decimal("100"),
                ma50=Decimal("96"),
                rsi_14=72.0,
                volume=820_000,
                avg_volume_20d=1_000_000,
                daily_change_pct=1.2,
                earnings_date=date.today() + timedelta(days=35),
            ),
        },
        {
            "setup_type": "borderline_overheated_constructive",
            "description": "Trend is positive, but RSI is between extended and clearly overheated.",
            "price": Decimal("104"),
            "snapshot": SimpleNamespace(
                moving_average_20=Decimal("100"),
                ma50=Decimal("96"),
                rsi_14=82.0,
                volume=820_000,
                avg_volume_20d=1_000_000,
                daily_change_pct=1.2,
                earnings_date=date.today() + timedelta(days=35),
            ),
        },
        {
            "setup_type": "clearly_overheated_constructive",
            "description": "Trend is positive, but RSI is clearly overheated enough to avoid.",
            "price": Decimal("104"),
            "snapshot": SimpleNamespace(
                moving_average_20=Decimal("100"),
                ma50=Decimal("96"),
                rsi_14=88.0,
                volume=820_000,
                avg_volume_20d=1_000_000,
                daily_change_pct=1.2,
                earnings_date=date.today() + timedelta(days=35),
            ),
        },
        {
            "setup_type": "weak_structure",
            "description": "Price is below MA20, MA20 is below MA50, and earnings are close.",
            "price": Decimal("96"),
            "snapshot": SimpleNamespace(
                moving_average_20=Decimal("100"),
                ma50=Decimal("104"),
                rsi_14=43.0,
                volume=650_000,
                avg_volume_20d=1_000_000,
                daily_change_pct=-1.4,
                earnings_date=date.today() + timedelta(days=5),
            ),
        },
    ]

    results = []
    for example in examples:
        snapshot = example["snapshot"]
        price = example["price"]
        evaluation = _evaluate_swing_rules(snapshot, price)
        action = _recommendation_action(evaluation)
        results.append(
            {
                "setup_type": example["setup_type"],
                "description": example["description"],
                "inputs": {
                    "price_vs_ma20_pct": round(evaluation["price_above_ma20_pct"], 2),
                    "ma20_vs_ma50_pct": round(evaluation["ma20_above_ma50_pct"], 2),
                    "rsi_14": snapshot.rsi_14,
                    "rsi_zone": evaluation["rsi_zone"],
                    "volume_ratio": round(evaluation["volume_ratio"], 2),
                    "daily_change_pct": snapshot.daily_change_pct,
                    "days_to_earnings": evaluation["days_to_earnings"],
                },
                "recommendation_action": action.value,
                "final_score": evaluation["final_score"],
                "passed_signals": evaluation["passed_signals"],
                "penalties": evaluation["penalties"],
                "avoid_reasons": evaluation["avoid_reasons"],
            }
        )
    return results


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
            "avoid_reasons": evaluation["avoid_reasons"],
            "final_score": evaluation["final_score"],
            "required_rules_passed": evaluation["required"],
            "rsi_zone": evaluation["rsi_zone"],
            "score_thresholds": {
                "buy": SWING_SCORE_THRESHOLDS["buy"],
                "watch": SWING_SCORE_THRESHOLDS["watch"],
                "avoid": SWING_SCORE_THRESHOLDS["avoid"],
            },
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
                "avoid_reasons": evaluation["avoid_reasons"],
                "final_score": evaluation["final_score"],
                "rule_metrics": {
                    "price_above_ma20_pct": round(evaluation["price_above_ma20_pct"], 2),
                    "ma20_above_ma50_pct": round(evaluation["ma20_above_ma50_pct"], 2),
                    "volume_ratio": round(evaluation["volume_ratio"], 2),
                    "rsi_zone": evaluation["rsi_zone"],
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
