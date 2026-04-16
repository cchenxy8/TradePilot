from decimal import Decimal

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from backend.app.models.enums import PositionAction
from backend.app.models.market_snapshot import MarketSnapshot
from backend.app.models.position import PortfolioPosition

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
    provider_rank = case(
        (
            MarketSnapshot.data_source_type.in_(["provider", "provider_delayed"]),
            1,
        ),
        else_=0,
    )
    return db.scalar(
        select(MarketSnapshot)
        .where(MarketSnapshot.symbol == symbol, MarketSnapshot.latest_price.is_not(None))
        .order_by(
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


def _pnl_pct(position: PortfolioPosition, price: Decimal | None) -> float | None:
    if position.average_cost is None or position.average_cost == 0 or price is None:
        return None
    return float(((price - position.average_cost) / position.average_cost) * 100)


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


def assess_position(db: Session, position: PortfolioPosition) -> dict:
    snapshot = _latest_symbol_snapshot(db, position.symbol)
    price = _position_price(position, snapshot)
    pnl_pct = _pnl_pct(position, price)
    snapshot_payload = None
    is_fund_like = _is_fund_like(position.symbol)

    if snapshot is not None:
        volume_ratio = snapshot.volume / snapshot.avg_volume_20d if snapshot.avg_volume_20d else None
        trend_positive = (
            price is not None
            and price >= snapshot.moving_average_20
            and snapshot.moving_average_20 >= snapshot.ma50
        )
        snapshot_payload = {
            "snapshot_price": float(price) if price is not None else None,
            "moving_average_20": float(snapshot.moving_average_20),
            "ma50": float(snapshot.ma50),
            "trend_positive": trend_positive,
            "rsi_14": snapshot.rsi_14,
            "volume_ratio": round(volume_ratio, 2) if volume_ratio is not None else None,
            "daily_change_pct": snapshot.daily_change_pct,
            "data_provider": snapshot.data_provider,
            "data_source_type": snapshot.data_source_type,
            "refreshed_at": snapshot.refreshed_at.isoformat(),
            "holding_type": "fund_or_index" if is_fund_like else "individual_stock",
        }
    else:
        volume_ratio = None
        trend_positive = None

    action = PositionAction.REVIEW
    rationale_parts: list[str] = []

    if price is None:
        action = PositionAction.REVIEW
        rationale_parts.append("Use Review because current price is missing.")
    elif position.average_cost is None:
        action = PositionAction.REVIEW
        rationale_parts.append("Use Review because average cost is missing and P/L context is incomplete.")
    elif snapshot is None:
        action = PositionAction.REVIEW
        rationale_parts.append("Use Review because no market snapshot is available yet.")
    else:
        concentrated = position.portfolio_weight is not None and position.portfolio_weight >= (0.35 if is_fund_like else 0.2)
        large_gain = pnl_pct is not None and pnl_pct >= (40 if is_fund_like else 25)
        loss_breakdown = pnl_pct is not None and pnl_pct <= (-12 if is_fund_like else -8)
        hot_momentum = snapshot.rsi_14 >= (82 if is_fund_like else 78)
        elevated_momentum = snapshot.rsi_14 >= 65
        light_volume = volume_ratio is not None and volume_ratio < 0.75

        if not trend_positive and loss_breakdown:
            action = PositionAction.EXIT
            rationale_parts.append("Use Exit because trend has weakened and the position is below cost.")
        elif concentrated or (large_gain and hot_momentum):
            action = PositionAction.TRIM
            rationale_parts.append(
                "Use Trim because exposure or profit risk is elevated."
                if concentrated
                else "Use Trim because the gain is large and momentum is hot."
            )
        elif trend_positive and not elevated_momentum and not light_volume and not concentrated:
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
            action = PositionAction.REVIEW
            rationale_parts.append("Use Review because trend is not constructive enough for Add or Hold conviction.")

        if trend_positive:
            rationale_parts.append("Trend structure is constructive with price above MA20 and MA20 above MA50.")
        else:
            rationale_parts.append("Trend structure is weak or incomplete relative to MA20 and MA50.")

        if pnl_pct is not None:
            rationale_parts.append(f"Position P/L is {pnl_pct:+.1f}% from average cost.")
        if hot_momentum:
            rationale_parts.append(f"RSI is hot at {snapshot.rsi_14:.1f}.")
        elif elevated_momentum:
            rationale_parts.append(f"RSI is elevated at {snapshot.rsi_14:.1f}.")
        else:
            rationale_parts.append(f"RSI is {snapshot.rsi_14:.1f}.")
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
