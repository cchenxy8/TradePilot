from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from backend.app.models.enums import PositionAction
from backend.app.models.market_snapshot import MarketSnapshot
from backend.app.models.position import PortfolioPosition
from backend.app.services.portfolio_assessment_config import PORTFOLIO_ASSESSMENT_THRESHOLDS

BROAD_FUND_SYMBOLS = {
    "SPY",
    "VOO",
    "IVV",
    "VTI",
    "QQQ",
    "QQQM",
    "DIA",
    "IWM",
    "SCHB",
    "SCHD",
    "VEA",
    "VWO",
    "VXUS",
    "BND",
    "AGG",
    "TLT",
    "XLK",
    "XLF",
    "XLE",
    "XLY",
    "XLP",
    "XLU",
    "XLV",
    "XLI",
    "XLB",
    "XLC",
    "SMH",
    "SOXX",
}


def _latest_symbol_snapshot(db: Session, symbol: str) -> MarketSnapshot | None:
    normalized_symbol = symbol.upper().strip()
    current_rank = case((MarketSnapshot.is_current.is_(True), 1), else_=0)
    provider_rank = case(
        (
            MarketSnapshot.data_source_type.in_(["provider", "provider_delayed"]),
            1,
        ),
        else_=0,
    )
    return db.scalar(
        select(MarketSnapshot)
        .where(MarketSnapshot.symbol == normalized_symbol, MarketSnapshot.latest_price.is_not(None))
        .order_by(
            current_rank.desc(),
            provider_rank.desc(),
            MarketSnapshot.refreshed_at.desc(),
            MarketSnapshot.updated_at.desc(),
            MarketSnapshot.id.desc(),
        )
        .limit(1)
    )


def _position_price(position: PortfolioPosition, snapshot: MarketSnapshot | None) -> Decimal | None:
    if position.current_price is not None:
        return position.current_price
    if snapshot is not None and snapshot.latest_price is not None:
        return snapshot.latest_price
    return None


def _snapshot_price(snapshot: MarketSnapshot | None) -> Decimal | None:
    if snapshot is not None and snapshot.latest_price is not None:
        return snapshot.latest_price
    return None


def _pnl_pct(position: PortfolioPosition, price: Decimal | None) -> float | None:
    if position.average_cost is None or position.average_cost == 0 or price is None:
        return None
    return float(((price - position.average_cost) / position.average_cost) * 100)


def _pct_distance(value: Decimal, reference: Decimal) -> float:
    if reference == 0:
        return 0.0
    return float(((value - reference) / reference) * 100)


def _price_mismatch_pct(position_price: Decimal | None, snapshot_price: Decimal | None) -> float | None:
    if position_price is None or snapshot_price is None or snapshot_price == 0:
        return None
    return float(((position_price - snapshot_price) / snapshot_price) * 100)


def _snapshot_age_hours(snapshot: MarketSnapshot) -> float:
    refreshed_at = snapshot.refreshed_at
    if refreshed_at.tzinfo is None:
        refreshed_at = refreshed_at.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - refreshed_at).total_seconds() / 3600


def _daily_change_for_decision(snapshot: MarketSnapshot) -> float | None:
    if abs(snapshot.daily_change_pct) >= _threshold("suspect_daily_change_abs_pct"):
        return None
    return snapshot.daily_change_pct


def _daily_change_is_suspect(snapshot: MarketSnapshot) -> bool:
    return _daily_change_for_decision(snapshot) is None


def _data_quality_warnings(
    snapshot: MarketSnapshot,
    volume_ratio: float | None,
    price_mismatch_pct: float | None,
    snapshot_age_hours: float,
) -> list[str]:
    warnings: list[str] = []
    if not snapshot.is_current:
        warnings.append("Snapshot is not marked current; portfolio selected it only because fresher current data was unavailable.")
    if snapshot_age_hours >= _threshold("snapshot_stale_hours"):
        warnings.append(f"Snapshot is stale at {snapshot_age_hours:.1f} hours old.")
    if abs(snapshot.daily_change_pct) >= _threshold("suspect_daily_change_abs_pct"):
        warnings.append(
            f"Daily change is unusually large at {snapshot.daily_change_pct:+.2f}%; it is visible for audit but excluded from action logic."
        )
    if volume_ratio is not None and volume_ratio >= _threshold("suspect_volume_ratio"):
        warnings.append(f"Volume ratio is unusually large at {volume_ratio:.2f}x; verify current and average volume inputs.")
    if snapshot.avg_volume_20d <= 0:
        warnings.append("Average volume is unavailable or zero, so volume ratio is not trustworthy.")
    if price_mismatch_pct is not None and abs(price_mismatch_pct) >= _threshold("position_snapshot_price_mismatch_pct"):
        warnings.append(
            f"Position price differs from the market snapshot by {price_mismatch_pct:+.1f}%; indicator metrics use snapshot price."
        )
    return warnings


def _is_fund_like(symbol: str) -> bool:
    normalized = symbol.upper().strip()
    return normalized in BROAD_FUND_SYMBOLS or normalized.endswith(("ETF", ".ETF"))


def _decision_text(action: PositionAction, is_fund_like: bool) -> str:
    if action == PositionAction.HOLD:
        return "Hold: keep the position and monitor the next market update."
    if action == PositionAction.ADD:
        return (
            "Add: consider increasing this broad holding after manual review."
            if is_fund_like
            else "Add: consider adding only if the thesis and risk plan still fit."
        )
    if action == PositionAction.TRIM:
        return "Trim: consider reducing exposure rather than adding risk."
    if action == PositionAction.EXIT:
        return "Exit: consider closing or materially reducing the position after manual review."
    return "Review: do not change the holding until the missing or conflicting signals are checked."


def _threshold(key: str) -> float:
    return PORTFOLIO_ASSESSMENT_THRESHOLDS[key]


def _position_flags(position: PortfolioPosition, pnl_pct: float | None, is_fund_like: bool) -> dict[str, bool]:
    concentration_threshold = _threshold("fund_concentration_weight" if is_fund_like else "stock_concentration_weight")
    large_gain_threshold = _threshold("fund_large_gain_pct" if is_fund_like else "stock_large_gain_pct")
    exit_loss_threshold = _threshold("fund_exit_loss_pct" if is_fund_like else "stock_exit_loss_pct")
    add_min_gain_threshold = _threshold("fund_add_min_gain_pct" if is_fund_like else "stock_add_min_gain_pct")
    return {
        "concentrated": position.portfolio_weight is not None and position.portfolio_weight >= concentration_threshold,
        "large_gain": pnl_pct is not None and pnl_pct >= large_gain_threshold,
        "loss_breakdown": pnl_pct is not None and pnl_pct <= exit_loss_threshold,
        "add_eligible_pnl": pnl_pct is None or pnl_pct >= add_min_gain_threshold,
    }


def _trim_gain_threshold(is_fund_like: bool, hot_momentum: bool, light_volume: bool) -> float:
    if hot_momentum and light_volume:
        return _threshold(
            "fund_trim_gain_with_hot_rsi_and_weak_volume_pct"
            if is_fund_like
            else "stock_trim_gain_with_hot_rsi_and_weak_volume_pct"
        )
    if hot_momentum:
        return _threshold("fund_trim_gain_with_hot_rsi_pct" if is_fund_like else "stock_trim_gain_with_hot_rsi_pct")
    return _threshold("fund_large_gain_pct" if is_fund_like else "stock_large_gain_pct")


def _late_overheated_trim_gain_threshold(is_fund_like: bool) -> float:
    return _threshold(
        "fund_late_overheated_trim_gain_pct" if is_fund_like else "stock_late_overheated_trim_gain_pct"
    )


def _late_elevated_trim_gain_threshold(is_fund_like: bool) -> float:
    return _threshold("fund_late_elevated_trim_gain_pct" if is_fund_like else "stock_late_elevated_trim_gain_pct")


def _late_light_volume_trim_gain_threshold(is_fund_like: bool) -> float:
    return _threshold(
        "fund_late_light_volume_trim_gain_pct" if is_fund_like else "stock_late_light_volume_trim_gain_pct"
    )


def _late_momentum_reasons(snapshot: MarketSnapshot, price: Decimal | None) -> tuple[bool, list[str], float | None]:
    reasons: list[str] = []
    price_vs_ma20 = _pct_distance(price, snapshot.moving_average_20) if price is not None else None
    daily_change_for_decision = _daily_change_for_decision(snapshot)

    if snapshot.rsi_14 >= _threshold("late_momentum_rsi"):
        reasons.append("RSI is already in a late-momentum range")
    if price_vs_ma20 is not None and price_vs_ma20 >= _threshold("late_momentum_price_above_ma20_pct"):
        reasons.append(f"price is {price_vs_ma20:.1f}% above MA20")
    if daily_change_for_decision is not None and daily_change_for_decision > _threshold("late_momentum_daily_change_pct"):
        reasons.append(f"daily move is strong at {daily_change_for_decision:.1f}%")

    return bool(reasons), reasons, price_vs_ma20


def _assess_without_snapshot(position: PortfolioPosition, pnl_pct: float | None, is_fund_like: bool) -> tuple[PositionAction, list[str]]:
    flags = _position_flags(position, pnl_pct, is_fund_like)
    if flags["concentrated"]:
        return PositionAction.TRIM, ["Use Trim because portfolio weight is high even without a fresh market snapshot."]
    if flags["loss_breakdown"]:
        return PositionAction.EXIT, ["Use Exit because the position is materially below cost and no market snapshot offsets that risk."]
    if flags["large_gain"]:
        return PositionAction.TRIM, ["Use Trim because the position has a large gain and imported data is enough to review exposure."]
    if flags["add_eligible_pnl"]:
        return PositionAction.HOLD, ["Use Hold because imported price and cost data are available, but market signals are missing."]
    return PositionAction.REVIEW, ["Use Review because imported data is too incomplete or conflicted for a clearer action."]


def assess_position(db: Session, position: PortfolioPosition) -> dict:
    snapshot = _latest_symbol_snapshot(db, position.symbol)
    position_price = _position_price(position, snapshot)
    market_price = _snapshot_price(snapshot)
    pnl_pct = _pnl_pct(position, position_price)
    snapshot_payload = None
    is_fund_like = _is_fund_like(position.symbol)

    if snapshot is not None:
        volume_ratio = snapshot.volume / snapshot.avg_volume_20d if snapshot.avg_volume_20d else None
        trend_positive = (
            market_price is not None
            and market_price >= snapshot.moving_average_20
            and snapshot.moving_average_20 >= snapshot.ma50
        )
        late_momentum, late_momentum_reasons, price_vs_ma20 = _late_momentum_reasons(snapshot, market_price)
        ma20_vs_ma50 = _pct_distance(snapshot.moving_average_20, snapshot.ma50)
        price_mismatch_pct = _price_mismatch_pct(position_price, market_price)
        snapshot_age_hours = _snapshot_age_hours(snapshot)
        daily_change_for_decision = _daily_change_for_decision(snapshot)
        daily_change_is_suspect = _daily_change_is_suspect(snapshot)
        data_quality_warnings = _data_quality_warnings(snapshot, volume_ratio, price_mismatch_pct, snapshot_age_hours)
        snapshot_payload = {
            "snapshot_price": float(market_price) if market_price is not None else None,
            "position_price": float(position_price) if position_price is not None else None,
            "moving_average_20": float(snapshot.moving_average_20),
            "ma50": float(snapshot.ma50),
            "trend_positive": trend_positive,
            "price_vs_ma20_pct": round(price_vs_ma20, 2) if price_vs_ma20 is not None else None,
            "ma20_vs_ma50_pct": round(ma20_vs_ma50, 2),
            "rsi_14": snapshot.rsi_14,
            "volume_ratio": round(volume_ratio, 2) if volume_ratio is not None else None,
            "daily_change_pct": snapshot.daily_change_pct,
            "daily_change_for_decision": daily_change_for_decision,
            "daily_change_is_suspect": daily_change_is_suspect,
            "data_provider": snapshot.data_provider,
            "data_source_type": snapshot.data_source_type,
            "refreshed_at": snapshot.refreshed_at.isoformat(),
            "snapshot_age_hours": round(snapshot_age_hours, 2),
            "is_current": snapshot.is_current,
            "field_sources": snapshot.field_sources,
            "data_quality_warnings": data_quality_warnings,
            "position_snapshot_price_mismatch_pct": round(price_mismatch_pct, 2) if price_mismatch_pct is not None else None,
            "holding_type": "fund_or_index" if is_fund_like else "individual_stock",
            "momentum_stage": "late_momentum" if late_momentum else "intact_or_emerging",
        }
    else:
        volume_ratio = None
        trend_positive = None
        late_momentum = False
        late_momentum_reasons = []
        price_vs_ma20 = None
        ma20_vs_ma50 = None
        price_mismatch_pct = None
        snapshot_age_hours = None
        daily_change_for_decision = None
        daily_change_is_suspect = False
        data_quality_warnings = []

    action = PositionAction.REVIEW
    rationale_parts: list[str] = []

    if position_price is None:
        action = PositionAction.REVIEW
        rationale_parts.append("Use Review because current price is missing.")
    elif position.average_cost is None:
        action = PositionAction.REVIEW
        rationale_parts.append("Use Review because average cost is missing and P/L context is incomplete.")
    elif snapshot is None:
        action, rationale_parts = _assess_without_snapshot(position, pnl_pct, is_fund_like)
    else:
        flags = _position_flags(position, pnl_pct, is_fund_like)
        concentrated = flags["concentrated"]
        loss_breakdown = flags["loss_breakdown"]
        add_eligible_pnl = flags["add_eligible_pnl"]
        hot_momentum = snapshot.rsi_14 >= _threshold("hot_rsi_fund" if is_fund_like else "hot_rsi_stock")
        elevated_momentum = snapshot.rsi_14 >= _threshold("elevated_rsi")
        light_volume = volume_ratio is not None and volume_ratio < _threshold("light_volume_ratio")
        extended_volume = volume_ratio is not None and volume_ratio >= _threshold("extended_volume_ratio")
        stretched_price = (
            price_vs_ma20 is not None and price_vs_ma20 >= _threshold("stretched_price_above_ma20_pct")
        )
        trim_gain_threshold = _trim_gain_threshold(is_fund_like, hot_momentum, light_volume)
        trim_pressure = pnl_pct is not None and pnl_pct >= trim_gain_threshold and (hot_momentum or light_volume)
        late_overheated_trim_pressure = (
            pnl_pct is not None
            and pnl_pct >= _late_overheated_trim_gain_threshold(is_fund_like)
            and hot_momentum
            and late_momentum
        )
        late_elevated_trim_pressure = (
            pnl_pct is not None
            and pnl_pct >= _late_elevated_trim_gain_threshold(is_fund_like)
            and elevated_momentum
            and late_momentum
            and (stretched_price or extended_volume)
        )
        late_light_volume_trim_pressure = (
            trend_positive
            and pnl_pct is not None
            and pnl_pct >= _late_light_volume_trim_gain_threshold(is_fund_like)
            and elevated_momentum
            and late_momentum
            and stretched_price
            and light_volume
        )

        if not trend_positive and loss_breakdown:
            action = PositionAction.EXIT
            rationale_parts.append("Use Exit because trend has weakened and the position is below cost.")
        elif (
            concentrated
            or trim_pressure
            or late_overheated_trim_pressure
            or late_elevated_trim_pressure
            or late_light_volume_trim_pressure
        ):
            action = PositionAction.TRIM
            if concentrated:
                rationale_parts.append("Use Trim because exposure or profit risk is elevated.")
            elif late_overheated_trim_pressure:
                rationale_parts.append(
                    "Use Trim because an existing profit cushion is paired with very hot, late-stage momentum."
                )
            elif late_elevated_trim_pressure:
                rationale_parts.append(
                    "Use Trim because a meaningful gain is paired with elevated, late-stage momentum and weaker reward-to-risk for adding."
                )
            elif late_light_volume_trim_pressure:
                rationale_parts.append(
                    "Use Trim because the position has a profit cushion, elevated late-stage momentum, stretched price, and weak volume confirmation."
                )
            else:
                rationale_parts.append("Use Trim because profit cushion, hot momentum, and/or weak volume are stacked.")
        elif trend_positive and not elevated_momentum and not light_volume and not concentrated and add_eligible_pnl:
            action = PositionAction.ADD
            rationale_parts.append(
                "Use Add because the broad holding is constructive and not concentrated."
                if is_fund_like
                else "Use Add because trend, RSI, and volume are aligned."
            )
        elif trend_positive:
            action = PositionAction.HOLD
            rationale_parts.append("Use Hold because trend is constructive, but one or more conditions argue against adding.")
        else:
            action = PositionAction.EXIT if loss_breakdown else PositionAction.HOLD
            rationale_parts.append(
                "Use Exit because losses and weak structure are aligned."
                if action == PositionAction.EXIT
                else "Use Hold because structure is not strong enough to add, but exit conditions are not met."
            )

        if trend_positive:
            rationale_parts.append("Trend structure is constructive with price above MA20 and MA20 above MA50.")
        else:
            rationale_parts.append("Trend structure is weak or incomplete relative to MA20 and MA50.")

        for warning in data_quality_warnings:
            rationale_parts.append(f"Data quality: {warning}")
        if pnl_pct is not None:
            rationale_parts.append(f"Position P/L is {pnl_pct:+.1f}% from average cost.")
        if hot_momentum:
            rationale_parts.append(f"RSI is hot at {snapshot.rsi_14:.1f}.")
        elif elevated_momentum:
            rationale_parts.append(f"RSI is elevated at {snapshot.rsi_14:.1f}.")
        else:
            rationale_parts.append(f"RSI is {snapshot.rsi_14:.1f}.")
        if late_momentum_reasons:
            rationale_parts.append(f"Late-momentum checks are active: {', '.join(late_momentum_reasons)}.")
        if daily_change_is_suspect:
            rationale_parts.append("Daily change was not used as a conviction signal because it failed the sanity check.")
        elif daily_change_for_decision is not None:
            rationale_parts.append(f"Daily change is {daily_change_for_decision:+.2f}% from trusted snapshot inputs.")
        if ma20_vs_ma50 is not None:
            rationale_parts.append(f"MA20 is {ma20_vs_ma50:+.1f}% versus MA50.")
        if stretched_price:
            rationale_parts.append("Price is stretched enough above MA20 to reduce add attractiveness.")
        if extended_volume:
            rationale_parts.append(f"Volume is elevated at {volume_ratio:.2f}x average, which can mark a crowded move.")
        if light_volume:
            rationale_parts.append(f"Volume confirmation is light at {volume_ratio:.2f}x average.")
        elif volume_ratio is not None:
            rationale_parts.append(f"Volume is {volume_ratio:.2f}x average.")
        if concentrated:
            rationale_parts.append(f"Portfolio weight is elevated at {position.portfolio_weight * 100:.1f}%.")
        if is_fund_like:
            rationale_parts.append("Broad ETF/index holdings are treated with wider bands than individual stocks.")

    if position.notes:
        rationale_parts.append("Saved notes should be considered before any manual decision.")

    summary = _decision_text(action, is_fund_like)

    return {
        "recommended_action": action,
        "assessment_summary": summary,
        "assessment_rationale": " ".join(rationale_parts),
        "pnl_pct": round(pnl_pct, 2) if pnl_pct is not None else None,
        "market_snapshot": snapshot_payload,
    }


def position_read_payload(db: Session, position: PortfolioPosition) -> dict:
    assessment = assess_position(db, position)
    return {
        "id": position.id,
        "account_id": position.account_id,
        "source_type": position.source_type,
        "external_position_id": position.external_position_id,
        "last_synced_at": position.last_synced_at,
        "symbol": position.symbol,
        "shares": position.shares,
        "average_cost": position.average_cost,
        "current_price": position.current_price,
        "unrealized_pnl": position.unrealized_pnl,
        "portfolio_weight": position.portfolio_weight,
        "thesis": position.thesis,
        "notes": position.notes,
        "recommended_action": assessment["recommended_action"],
        "assessment_summary": assessment["assessment_summary"],
        "assessment_rationale": assessment["assessment_rationale"],
        "pnl_pct": assessment["pnl_pct"],
        "market_snapshot": assessment["market_snapshot"],
        "created_at": position.created_at,
        "updated_at": position.updated_at,
    }
