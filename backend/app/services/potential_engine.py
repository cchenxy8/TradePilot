from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.enums import BucketType
from backend.app.models.watchlist import WatchlistItem
from backend.app.services.market_data import (
    get_active_snapshot_for_item,
    is_provider_backed,
    snapshot_price,
)
from backend.app.services.potential_scoring_config import (
    POTENTIAL_RULE_BOUNDS,
    POTENTIAL_SCORE_BASE,
    POTENTIAL_SCORE_BONUSES,
    POTENTIAL_SCORE_LIMITS,
    POTENTIAL_SCORE_PENALTIES,
    POTENTIAL_STAGE_SCORE_CAPS,
    POTENTIAL_SCORE_THRESHOLDS,
)


def _pct_distance(value: Decimal, reference: Decimal) -> float:
    if reference == 0:
        return 0.0
    return float(((value - reference) / reference) * 100)


def evaluate_potential_signal(snapshot, price: Decimal) -> dict:
    price_vs_ma20 = _pct_distance(price, snapshot.moving_average_20)
    ma20_vs_ma50 = _pct_distance(snapshot.moving_average_20, snapshot.ma50)
    volume_ratio = snapshot.volume / snapshot.avg_volume_20d if snapshot.avg_volume_20d else 0.0
    late_momentum = (
        snapshot.rsi_14 >= POTENTIAL_RULE_BOUNDS["rsi_late_momentum"]
        or price_vs_ma20 >= POTENTIAL_RULE_BOUNDS["price_late_extension_above_ma20_pct"]
        or snapshot.daily_change_pct > POTENTIAL_RULE_BOUNDS["momentum_strong_max_pct"]
    )

    developing_signals: list[str] = []
    cautions: list[str] = []
    score = POTENTIAL_SCORE_BASE

    if 0 <= price_vs_ma20 <= POTENTIAL_RULE_BOUNDS["price_reclaim_max_above_ma20_pct"]:
        score += POTENTIAL_SCORE_BONUSES["price_reclaimed_ma20"]
        developing_signals.append("Price has reclaimed the 20-day moving average without being far extended.")
    elif POTENTIAL_RULE_BOUNDS["price_near_reclaim_min_pct"] <= price_vs_ma20 < 0:
        score += POTENTIAL_SCORE_BONUSES["price_near_ma20_reclaim"]
        developing_signals.append("Price is close to reclaiming the 20-day moving average.")
    elif price_vs_ma20 < POTENTIAL_RULE_BOUNDS["price_far_below_ma20_pct"]:
        score -= POTENTIAL_SCORE_PENALTIES["price_far_below_ma20"]
        cautions.append("Price remains well below the 20-day moving average.")

    if ma20_vs_ma50 >= 0:
        score += POTENTIAL_SCORE_BONUSES["ma20_above_ma50"]
        developing_signals.append("MA20 is above MA50, so the short-term trend structure is improving or intact.")
    elif ma20_vs_ma50 >= POTENTIAL_RULE_BOUNDS["ma20_close_to_ma50_min_pct"]:
        score += POTENTIAL_SCORE_BONUSES["ma20_close_to_ma50"]
        developing_signals.append("MA20 is close to MA50, which can mark an early repair zone.")
    elif ma20_vs_ma50 < POTENTIAL_RULE_BOUNDS["ma20_far_below_ma50_pct"]:
        score -= POTENTIAL_SCORE_PENALTIES["ma20_far_below_ma50"]
        cautions.append("MA20 is still meaningfully below MA50.")

    if POTENTIAL_RULE_BOUNDS["rsi_recovering_min"] <= snapshot.rsi_14 <= POTENTIAL_RULE_BOUNDS["rsi_recovering_max"]:
        score += POTENTIAL_SCORE_BONUSES["rsi_recovering"]
        developing_signals.append("RSI is in a recovering range, not yet overheated.")
    elif POTENTIAL_RULE_BOUNDS["rsi_recovering_max"] < snapshot.rsi_14 <= POTENTIAL_RULE_BOUNDS["rsi_constructive_max"]:
        score += POTENTIAL_SCORE_BONUSES["rsi_constructive"]
        developing_signals.append("RSI is constructive while still below overheated levels.")
    elif snapshot.rsi_14 >= POTENTIAL_RULE_BOUNDS["rsi_overheated"]:
        score -= POTENTIAL_SCORE_PENALTIES["rsi_overheated"]
        cautions.append("RSI is already hot, so this may be late rather than early.")
    elif snapshot.rsi_14 < POTENTIAL_RULE_BOUNDS["rsi_weak"]:
        score -= POTENTIAL_SCORE_PENALTIES["rsi_weak"]
        cautions.append("RSI is still weak.")

    if volume_ratio >= POTENTIAL_RULE_BOUNDS["volume_improving_ratio"]:
        score += POTENTIAL_SCORE_BONUSES["volume_improving"]
        developing_signals.append(f"Volume is improving at {volume_ratio:.2f}x the 20-day average.")
    elif volume_ratio >= POTENTIAL_RULE_BOUNDS["volume_near_average_ratio"]:
        score += POTENTIAL_SCORE_BONUSES["volume_near_average"]
        developing_signals.append(f"Volume is near average at {volume_ratio:.2f}x.")
    elif volume_ratio < POTENTIAL_RULE_BOUNDS["volume_light_ratio"]:
        score -= POTENTIAL_SCORE_PENALTIES["volume_light"]
        cautions.append(f"Volume remains light at {volume_ratio:.2f}x average.")

    if (
        POTENTIAL_RULE_BOUNDS["momentum_improving_min_pct"]
        <= snapshot.daily_change_pct
        <= POTENTIAL_RULE_BOUNDS["momentum_strong_max_pct"]
    ):
        score += POTENTIAL_SCORE_BONUSES["momentum_improving"]
        developing_signals.append(f"Daily momentum is improving at {snapshot.daily_change_pct:.2f}%.")
    elif snapshot.daily_change_pct > POTENTIAL_RULE_BOUNDS["momentum_strong_max_pct"]:
        score += POTENTIAL_SCORE_BONUSES["relative_strength_proxy"]
        cautions.append("Daily move is strong enough that chasing risk should be checked.")
    elif snapshot.daily_change_pct < 0:
        score -= POTENTIAL_SCORE_PENALTIES["momentum_negative"]
        cautions.append(f"Daily momentum is still negative at {snapshot.daily_change_pct:.2f}%.")

    if late_momentum:
        score -= POTENTIAL_SCORE_PENALTIES["late_momentum"]
        score = min(score, POTENTIAL_STAGE_SCORE_CAPS["late_momentum"])
        cautions.append("This looks more like late momentum than an early discovery setup.")
        setup_stage = "late_momentum"
        stage_label = "Late momentum"
    else:
        setup_stage = "emerging_potential"
        stage_label = "Emerging potential"

    score = min(max(round(score, 2), POTENTIAL_SCORE_LIMITS["min"]), POTENTIAL_SCORE_LIMITS["max"])
    if score >= POTENTIAL_SCORE_THRESHOLDS["high"]:
        flag = "high"
    elif score >= POTENTIAL_SCORE_THRESHOLDS["medium"]:
        flag = "medium"
    else:
        flag = "low"

    lead_signal = developing_signals[0] if developing_signals else "No strong early-development signal is visible yet."
    lead_caution = cautions[0] if cautions else "Still requires standard confirmation before any entry decision."
    rationale = (
        f"{lead_signal} {lead_caution} "
        f"Classified as {stage_label.lower()}. "
        "This is a discovery indicator, not a confirmed entry signal or buy instruction."
    )

    return {
        "potential_score": score,
        "potential_flag": flag,
        "setup_stage": setup_stage,
        "stage_label": stage_label,
        "rationale": rationale,
        "developing_signals": developing_signals,
        "cautions": cautions,
        "label": stage_label,
        "warning": "Do not treat potential as Buy. It only surfaces names for manual research before standard confirmation.",
        "metrics": {
            "price_vs_ma20_pct": round(price_vs_ma20, 2),
            "ma20_vs_ma50_pct": round(ma20_vs_ma50, 2),
            "rsi_14": snapshot.rsi_14,
            "volume_ratio": round(volume_ratio, 2),
            "daily_change_pct": snapshot.daily_change_pct,
        },
        "score_thresholds": POTENTIAL_SCORE_THRESHOLDS,
    }


def scan_potential_universe(db: Session, bucket: BucketType | None = None, limit: int = 12) -> list[dict]:
    query = (
        select(WatchlistItem)
        .where(WatchlistItem.is_active.is_(True))
        .order_by(WatchlistItem.symbol.asc())
    )
    if bucket is not None:
        query = query.where(WatchlistItem.bucket == bucket)

    candidates: list[dict] = []
    for item in db.scalars(query):
        snapshot = get_active_snapshot_for_item(db, item)
        if snapshot is None:
            continue
        price = snapshot_price(snapshot)
        signal = evaluate_potential_signal(snapshot, price)
        candidates.append(
            {
                "symbol": item.symbol,
                "bucket": item.bucket.value,
                "watchlist_item_id": item.id,
                "thesis": item.thesis,
                "potential_score": signal["potential_score"],
                "potential_flag": signal["potential_flag"],
                "setup_stage": signal["setup_stage"],
                "stage_label": signal["stage_label"],
                "rationale": signal["rationale"],
                "developing_signals": signal["developing_signals"],
                "cautions": signal["cautions"],
                "warning": signal["warning"],
                "metrics": signal["metrics"],
                "market_snapshot": {
                    "snapshot_price": float(price),
                    "data_provider": snapshot.data_provider,
                    "data_source_type": snapshot.data_source_type,
                    "refreshed_at": snapshot.refreshed_at.isoformat(),
                    "is_provider_backed": is_provider_backed(snapshot),
                },
            }
        )

    discovery_candidates = [
        candidate
        for candidate in candidates
        if candidate["potential_flag"] != "low" or candidate["setup_stage"] == "late_momentum"
    ]
    stage_rank = {"emerging_potential": 0, "late_momentum": 1}
    return sorted(
        discovery_candidates,
        key=lambda candidate: (
            stage_rank.get(candidate["setup_stage"], 2),
            -candidate["potential_score"],
            candidate["symbol"],
        ),
    )[:limit]
