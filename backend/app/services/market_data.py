from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from statistics import mean
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy import case, select
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
    source_type: str
    delay_note: str
    field_sources: dict[str, str]
    payload: dict


class MarketDataError(RuntimeError):
    pass


class MarketDataRefreshError(MarketDataError):
    def __init__(self, failures: list[dict[str, str]]) -> None:
        self.failures = failures
        super().__init__("Unable to refresh market data for any active watchlist symbols")


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
    refreshed_at = datetime.now(timezone.utc)
    for item in watchlist_items:
        try:
            snapshots.append(create_market_snapshot_for_item(db, item, refreshed_at=refreshed_at))
        except MarketDataError as error:
            failures.append({"symbol": item.symbol, "error": str(error)})

    log_event(
        db,
        event_type="market_data.refresh",
        entity_type="market_snapshot",
        entity_id=None,
        payload={
            "provider": settings.market_data_provider,
            "source_type": "provider_delayed",
            "delay_note": _provider_delay_note(),
            "refreshed_at": refreshed_at.isoformat(),
            "snapshots_created": len(snapshots),
            "failures": failures,
        },
    )
    db.commit()
    if failures and not snapshots:
        raise MarketDataRefreshError(failures)
    for snapshot in snapshots:
        db.refresh(snapshot)
    return snapshots


def list_active_market_snapshots(db: Session) -> list[MarketSnapshot]:
    watchlist_items = list(
        db.scalars(
            select(WatchlistItem)
            .where(WatchlistItem.is_active.is_(True))
            .order_by(WatchlistItem.symbol.asc())
        )
    )
    snapshots: list[MarketSnapshot] = []
    for item in watchlist_items:
        snapshot = get_active_snapshot_for_item(db, item)
        if snapshot is not None:
            snapshots.append(snapshot)
    return snapshots


def create_market_snapshot_for_item(
    db: Session,
    item: WatchlistItem,
    refreshed_at: datetime | None = None,
) -> MarketSnapshot:
    quote = fetch_market_quote(item.symbol)
    return _create_snapshot_from_quote(db, quote, item.id, refreshed_at)


def create_market_snapshot_for_symbol(db: Session, symbol: str, watchlist_item_id: int | None = None) -> MarketSnapshot:
    quote = fetch_market_quote(symbol)
    return _create_snapshot_from_quote(db, quote, watchlist_item_id)


def get_fresh_provider_snapshot_for_item(
    db: Session,
    item: WatchlistItem,
    max_age: timedelta = timedelta(hours=6),
) -> MarketSnapshot:
    snapshot = get_active_snapshot_for_item(db, item)
    if snapshot is not None and is_provider_backed(snapshot):
        now = datetime.now(timezone.utc)
        refreshed_at = snapshot.refreshed_at
        if refreshed_at.tzinfo is None:
            refreshed_at = refreshed_at.replace(tzinfo=timezone.utc)
        if now - refreshed_at <= max_age:
            return snapshot

    return create_market_snapshot_for_item(db, item)


def get_active_snapshot_with_refresh_attempt(db: Session, item: WatchlistItem) -> MarketSnapshot | None:
    active_snapshot = get_active_snapshot_for_item(db, item)
    try:
        return create_market_snapshot_for_item(db, item)
    except MarketDataError:
        return active_snapshot


def is_provider_backed(snapshot: MarketSnapshot) -> bool:
    return snapshot.data_source_type in {"provider", "provider_delayed"} and snapshot.latest_price is not None


def get_active_snapshot_for_item(db: Session, item: WatchlistItem) -> MarketSnapshot | None:
    return db.scalar(_active_snapshot_query(item.id, item.symbol).limit(1))


def _active_snapshot_query(watchlist_item_id: int, symbol: str):
    provider_rank = case(
        (
            MarketSnapshot.data_source_type.in_(["provider", "provider_delayed"]),
            1,
        ),
        else_=0,
    )
    return (
        select(MarketSnapshot)
        .where(
            MarketSnapshot.watchlist_item_id == watchlist_item_id,
            MarketSnapshot.symbol == symbol,
            MarketSnapshot.latest_price.is_not(None),
        )
        .order_by(
            provider_rank.desc(),
            MarketSnapshot.refreshed_at.desc(),
            MarketSnapshot.updated_at.desc(),
            MarketSnapshot.id.desc(),
        )
    )


def _create_snapshot_from_quote(
    db: Session,
    quote: MarketQuote,
    watchlist_item_id: int | None,
    refreshed_at: datetime | None = None,
) -> MarketSnapshot:
    timestamp = refreshed_at or datetime.now(timezone.utc)
    payload = {
        **quote.payload,
        "provider": quote.provider,
        "source_type": quote.source_type,
        "delay_note": quote.delay_note,
        "field_sources": quote.field_sources,
        "refreshed_at": timestamp.isoformat(),
    }
    _mark_existing_snapshots_not_current(db, quote.symbol, watchlist_item_id)
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
        data_provider=quote.provider,
        data_source_type=quote.source_type,
        data_delay_note=quote.delay_note,
        field_sources=quote.field_sources,
        is_current=True,
        refreshed_at=timestamp,
        captured_at=timestamp,
        snapshot_payload=payload,
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def _mark_existing_snapshots_not_current(
    db: Session,
    symbol: str,
    watchlist_item_id: int | None,
) -> None:
    query = select(MarketSnapshot).where(MarketSnapshot.symbol == symbol, MarketSnapshot.is_current.is_(True))
    if watchlist_item_id is None:
        query = query.where(MarketSnapshot.watchlist_item_id.is_(None))
    else:
        query = query.where(MarketSnapshot.watchlist_item_id == watchlist_item_id)

    for snapshot in db.scalars(query):
        snapshot.is_current = False


def get_latest_snapshot_for_item(db: Session, item: WatchlistItem) -> MarketSnapshot | None:
    return get_active_snapshot_for_item(db, item)


def snapshot_price(snapshot: MarketSnapshot) -> Decimal:
    if snapshot.latest_price is not None:
        return snapshot.latest_price
    if snapshot.mock_price is not None:
        return snapshot.mock_price
    raise MarketDataError(f"Snapshot {snapshot.id} for {snapshot.symbol} has no price")


def _fetch_yahoo_quote(symbol: str) -> MarketQuote:
    normalized = symbol.upper().strip()
    quote_error: str | None = None
    try:
        quote = _fetch_json(
            "/v7/finance/quote",
            {"symbols": normalized},
        )
    except MarketDataError as error:
        quote = {}
        quote_error = str(error)
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

    raw_latest_price = quote_row.get("regularMarketPrice")
    latest_price_source = "yahoo_quote.regularMarketPrice"
    if raw_latest_price is None:
        raw_latest_price = meta.get("regularMarketPrice")
        latest_price_source = "yahoo_chart.meta.regularMarketPrice"
    if raw_latest_price is None:
        raw_latest_price = meta.get("previousClose")
        latest_price_source = "yahoo_chart.meta.previousClose"
    if raw_latest_price is None and closes:
        raw_latest_price = closes[-1]
        latest_price_source = "yahoo_chart.latest_daily_close"

    latest_price = _decimal_from(raw_latest_price)
    if latest_price is None:
        raise MarketDataError(f"No latest price returned for {normalized}")

    daily_change_pct = quote_row.get("regularMarketChangePercent")
    daily_change_source = "yahoo_quote.regularMarketChangePercent"
    if daily_change_pct is None:
        previous_close = (
            quote_row.get("regularMarketPreviousClose")
            or meta.get("previousClose")
            or meta.get("chartPreviousClose")
            or (closes[-2] if len(closes) >= 2 else None)
        )
        daily_change_pct = _calculate_change_pct(float(latest_price), previous_close)
        daily_change_source = "derived_from_latest_price_and_previous_close"

    avg_volume_20d = int(mean(volumes[-20:])) if volumes else int(quote_row.get("averageDailyVolume10Day") or 0)
    avg_volume_source = "derived_from_yahoo_chart_3mo_daily_volume" if volumes else "yahoo_quote.averageDailyVolume10Day"
    raw_volume = quote_row.get("regularMarketVolume")
    volume_source = "yahoo_quote.regularMarketVolume"
    if raw_volume is None:
        raw_volume = meta.get("regularMarketVolume")
        volume_source = "yahoo_chart.meta.regularMarketVolume"
    if raw_volume is None:
        raw_volume = volumes[-1] if volumes else 0
        volume_source = "yahoo_chart.latest_daily_volume"
    volume = int(raw_volume)
    moving_average_20 = _decimal_from(mean(closes[-20:]) if closes else latest_price) or latest_price
    ma50 = _decimal_from(mean(closes[-50:]) if len(closes) >= 50 else moving_average_20) or moving_average_20
    rsi_14 = _calculate_rsi(closes)
    earnings_date = _extract_earnings_date(quote_row)
    earnings_source = (
        "yahoo_quote.earningsTimestamp_or_earningsTimestampStart"
        if quote_row
        else "unavailable_quote_endpoint_rejected_or_empty"
    )
    field_sources = {
        "latest_price": latest_price_source,
        "daily_change_pct": daily_change_source,
        "volume": volume_source,
        "earnings_date": earnings_source,
        "avg_volume_20d": avg_volume_source,
        "moving_average_20": "derived_from_yahoo_chart_3mo_daily_close",
        "ma50": "derived_from_yahoo_chart_3mo_daily_close",
        "rsi_14": "derived_from_yahoo_chart_3mo_daily_close",
    }

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
        "source_type": "provider_delayed",
        "delay_note": _provider_delay_note(),
        "field_sources": field_sources,
        "provider_warnings": [quote_error] if quote_error else [],
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
        source_type="provider_delayed",
        delay_note=_provider_delay_note(),
        field_sources=field_sources,
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
        f"on volume of {quote.volume:,}. Data provider: {quote.provider}; {quote.delay_note}"
    )


def _provider_delay_note() -> str:
    return "Yahoo public market data can be delayed and may not match real-time brokerage quotes."
