from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from statistics import mean
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.market_snapshot import MarketSnapshot
from backend.app.models.watchlist import WatchlistItem
from backend.app.services.audit import log_event


@dataclass(frozen=True)
class MarketQuote:
    symbol: str
    latest_price: Decimal
    daily_change_pct: float
    volume: int
    avg_volume_20d: int
    moving_average_20: Decimal
    ma50: Decimal
    rsi_14: float
    earnings_date: date | None
    provider: str
    payload: dict


class MarketDataError(RuntimeError):
    pass


def fetch_market_quote(symbol: str) -> MarketQuote:
    if settings.market_data_provider.lower() != "yahoo":
        raise MarketDataError(f"Unsupported market data provider: {settings.market_data_provider}")
    return _fetch_yahoo_quote(symbol)


def refresh_watchlist_market_snapshots(db: Session) -> list[MarketSnapshot]:
    watchlist_items = list(
        db.scalars(
            select(WatchlistItem)
            .where(WatchlistItem.is_active.is_(True))
            .order_by(WatchlistItem.symbol.asc())
        )
    )

    snapshots: list[MarketSnapshot] = []
    failures: list[dict[str, str]] = []
    for item in watchlist_items:
        try:
            snapshots.append(create_market_snapshot_for_item(db, item))
        except MarketDataError as error:
            failures.append({"symbol": item.symbol, "error": str(error)})

    log_event(
        db,
        event_type="market_data.refresh",
        entity_type="market_snapshot",
        entity_id=None,
        payload={
            "provider": settings.market_data_provider,
            "snapshots_created": len(snapshots),
            "failures": failures,
        },
    )
    db.commit()
    for snapshot in snapshots:
        db.refresh(snapshot)
    return snapshots


def create_market_snapshot_for_item(db: Session, item: WatchlistItem) -> MarketSnapshot:
    quote = fetch_market_quote(item.symbol)
    snapshot = MarketSnapshot(
        symbol=quote.symbol,
        watchlist_item_id=item.id,
        latest_price=quote.latest_price,
        mock_price=None,
        volume=quote.volume,
        avg_volume_20d=quote.avg_volume_20d,
        moving_average_20=quote.moving_average_20,
        ma50=quote.ma50,
        daily_change_pct=quote.daily_change_pct,
        rsi_14=quote.rsi_14,
        earnings_date=quote.earnings_date,
        news_summary=_build_market_summary(quote),
        snapshot_payload=quote.payload,
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def create_market_snapshot_for_symbol(db: Session, symbol: str, watchlist_item_id: int | None = None) -> MarketSnapshot:
    quote = fetch_market_quote(symbol)
    snapshot = MarketSnapshot(
        symbol=quote.symbol,
        watchlist_item_id=watchlist_item_id,
        latest_price=quote.latest_price,
        mock_price=None,
        volume=quote.volume,
        avg_volume_20d=quote.avg_volume_20d,
        moving_average_20=quote.moving_average_20,
        ma50=quote.ma50,
        daily_change_pct=quote.daily_change_pct,
        rsi_14=quote.rsi_14,
        earnings_date=quote.earnings_date,
        news_summary=_build_market_summary(quote),
        snapshot_payload=quote.payload,
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def get_latest_snapshot_for_item(db: Session, item: WatchlistItem) -> MarketSnapshot | None:
    return db.scalar(
        select(MarketSnapshot)
        .where(MarketSnapshot.watchlist_item_id == item.id)
        .order_by(MarketSnapshot.captured_at.desc())
        .limit(1)
    )


def snapshot_price(snapshot: MarketSnapshot) -> Decimal:
    if snapshot.latest_price is not None:
        return snapshot.latest_price
    if snapshot.mock_price is not None:
        return snapshot.mock_price
    raise MarketDataError(f"Snapshot {snapshot.id} for {snapshot.symbol} has no price")


def _fetch_yahoo_quote(symbol: str) -> MarketQuote:
    normalized = symbol.upper().strip()
    quote = _fetch_json(
        "/v7/finance/quote",
        {"symbols": normalized},
    )
    result = quote.get("quoteResponse", {}).get("result", [])
    quote_row = result[0] if result else {}

    chart = _fetch_json(
        f"/v8/finance/chart/{normalized}",
        {"range": "3mo", "interval": "1d"},
    )
    chart_result = chart.get("chart", {}).get("result", [])
    if not chart_result:
        raise MarketDataError(f"No chart data returned for {normalized}")

    chart_row = chart_result[0]
    indicators = chart_row.get("indicators", {}).get("quote", [{}])[0]
    closes = _clean_numbers(indicators.get("close", []))
    volumes = [int(value) for value in indicators.get("volume", []) or [] if value is not None]
    meta = chart_row.get("meta", {})

    latest_price = _decimal_from(
        quote_row.get("regularMarketPrice")
        or meta.get("regularMarketPrice")
        or meta.get("previousClose")
        or (closes[-1] if closes else None)
    )
    if latest_price is None:
        raise MarketDataError(f"No latest price returned for {normalized}")

    daily_change_pct = quote_row.get("regularMarketChangePercent")
    if daily_change_pct is None:
        previous_close = quote_row.get("regularMarketPreviousClose") or meta.get("previousClose")
        daily_change_pct = _calculate_change_pct(float(latest_price), previous_close)

    avg_volume_20d = int(mean(volumes[-20:])) if volumes else int(quote_row.get("averageDailyVolume10Day") or 0)
    volume = int(quote_row.get("regularMarketVolume") or (volumes[-1] if volumes else 0))
    moving_average_20 = _decimal_from(mean(closes[-20:]) if closes else latest_price) or latest_price
    ma50 = _decimal_from(mean(closes[-50:]) if len(closes) >= 50 else moving_average_20) or moving_average_20
    rsi_14 = _calculate_rsi(closes)
    earnings_date = _extract_earnings_date(quote_row)

    payload = {
        "symbol": normalized,
        "latest_price": float(latest_price),
        "daily_change_pct": round(float(daily_change_pct or 0), 2),
        "volume": volume,
        "avg_volume_20d": avg_volume_20d,
        "moving_average_20": float(moving_average_20),
        "ma50": float(ma50),
        "rsi_14": rsi_14,
        "earnings_date": earnings_date.isoformat() if earnings_date else None,
        "provider": settings.market_data_provider,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    return MarketQuote(
        symbol=normalized,
        latest_price=latest_price,
        daily_change_pct=round(float(daily_change_pct or 0), 2),
        volume=volume,
        avg_volume_20d=avg_volume_20d,
        moving_average_20=moving_average_20,
        ma50=ma50,
        rsi_14=rsi_14,
        earnings_date=earnings_date,
        provider=settings.market_data_provider,
        payload=payload,
    )


def _fetch_json(path: str, query: dict[str, str]) -> dict:
    url = f"{settings.market_data_base_url}{path}?{urlencode(query)}"
    request = Request(
        url,
        headers={
            "User-Agent": "TradePilot/0.1 market-data research tool",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=settings.market_data_timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as error:  # noqa: BLE001 - converted to app-level service error
        raise MarketDataError(f"Unable to fetch market data from {url}: {error}") from error


def _decimal_from(value: object) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(round(float(value), 2)))


def _clean_numbers(values: list[object]) -> list[float]:
    return [float(value) for value in values if value is not None]


def _calculate_change_pct(latest_price: float, previous_close: object) -> float:
    if previous_close in (None, 0):
        return 0.0
    previous = float(previous_close)
    if previous == 0:
        return 0.0
    return round(((latest_price - previous) / previous) * 100, 2)


def _calculate_rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) <= period:
        return 50.0

    gains: list[float] = []
    losses: list[float] = []
    for previous, current in zip(closes[-period - 1 : -1], closes[-period:], strict=True):
        change = current - previous
        gains.append(max(change, 0.0))
        losses.append(abs(min(change, 0.0)))

    avg_gain = mean(gains)
    avg_loss = mean(losses)
    if avg_loss == 0:
        return 100.0
    relative_strength = avg_gain / avg_loss
    return round(100 - (100 / (1 + relative_strength)), 1)


def _extract_earnings_date(quote_row: dict) -> date | None:
    timestamp = quote_row.get("earningsTimestamp") or quote_row.get("earningsTimestampStart")
    if timestamp is None:
        return None
    return datetime.fromtimestamp(int(timestamp), tz=timezone.utc).date()


def _build_market_summary(quote: MarketQuote) -> str:
    direction = "up" if quote.daily_change_pct >= 0 else "down"
    return (
        f"{quote.symbol} is {direction} {abs(quote.daily_change_pct):.2f}% today "
        f"on volume of {quote.volume:,}. Data provider: {quote.provider}."
    )
