from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.enums import (
    BucketType,
    ComplianceStatus,
    RecommendationType,
)
from backend.app.models.market_snapshot import MarketSnapshot
from backend.app.models.recommendation import Recommendation
from backend.app.models.watchlist import WatchlistItem
from backend.app.services.audit import log_event


ASSET_SEEDS = [
    {
        "symbol": "AAPL",
        "bucket": BucketType.CORE,
        "thesis": "Large-cap quality compounder with durable ecosystem strength.",
        "mock_price": Decimal("212.40"),
        "volume": 74200000,
        "moving_average_20": Decimal("205.10"),
        "rsi_14": 61.5,
        "earnings_offset_days": 26,
        "news_summary": "Services growth stays resilient while hardware demand stabilizes.",
    },
    {
        "symbol": "MSFT",
        "bucket": BucketType.CORE,
        "thesis": "Cloud and AI platform leader with steady institutional sponsorship.",
        "mock_price": Decimal("428.60"),
        "volume": 31100000,
        "moving_average_20": Decimal("420.80"),
        "rsi_14": 58.2,
        "earnings_offset_days": 19,
        "news_summary": "Enterprise AI adoption remains supportive for cloud sentiment.",
    },
    {
        "symbol": "AMZN",
        "bucket": BucketType.CORE,
        "thesis": "Retail and cloud mix offers multi-engine earnings expansion.",
        "mock_price": Decimal("189.25"),
        "volume": 46800000,
        "moving_average_20": Decimal("184.90"),
        "rsi_14": 55.4,
        "earnings_offset_days": 21,
        "news_summary": "Margin discipline offsets mixed consumer spending data.",
    },
    {
        "symbol": "NVDA",
        "bucket": BucketType.SWING,
        "thesis": "Momentum leader with strong relative strength and AI tailwinds.",
        "mock_price": Decimal("941.70"),
        "volume": 59300000,
        "moving_average_20": Decimal("902.30"),
        "rsi_14": 67.9,
        "earnings_offset_days": 18,
        "news_summary": "Supply commentary and AI demand headlines remain supportive.",
    },
    {
        "symbol": "AMD",
        "bucket": BucketType.SWING,
        "thesis": "Chip cycle participation with improving data-center narrative.",
        "mock_price": Decimal("173.90"),
        "volume": 52400000,
        "moving_average_20": Decimal("165.10"),
        "rsi_14": 63.4,
        "earnings_offset_days": 15,
        "news_summary": "Data center product cycle keeps sentiment constructive.",
    },
    {
        "symbol": "META",
        "bucket": BucketType.SWING,
        "thesis": "Ad efficiency and engagement improvements support trend continuation.",
        "mock_price": Decimal("512.80"),
        "volume": 20700000,
        "moving_average_20": Decimal("500.40"),
        "rsi_14": 59.7,
        "earnings_offset_days": 17,
        "news_summary": "Ad pricing and AI engagement headlines support upside follow-through.",
    },
    {
        "symbol": "TSLA",
        "bucket": BucketType.SWING,
        "thesis": "High-beta swing name with event-driven volatility and retail interest.",
        "mock_price": Decimal("187.30"),
        "volume": 108200000,
        "moving_average_20": Decimal("193.40"),
        "rsi_14": 42.8,
        "earnings_offset_days": 11,
        "news_summary": "Delivery and margin concerns continue to pressure trend quality.",
    },
    {
        "symbol": "SNOW",
        "bucket": BucketType.EVENT,
        "thesis": "Event-driven setup tied to product launches and guidance revisions.",
        "mock_price": Decimal("171.20"),
        "volume": 7600000,
        "moving_average_20": Decimal("167.90"),
        "rsi_14": 53.3,
        "earnings_offset_days": 9,
        "news_summary": "Platform announcements may reshape near-term growth expectations.",
    },
    {
        "symbol": "SHOP",
        "bucket": BucketType.EVENT,
        "thesis": "Merchant growth and product roadmap create catalyst-driven upside.",
        "mock_price": Decimal("78.40"),
        "volume": 12400000,
        "moving_average_20": Decimal("75.50"),
        "rsi_14": 57.1,
        "earnings_offset_days": 13,
        "news_summary": "Merchant tools rollout and margin story improve event interest.",
    },
    {
        "symbol": "PLTR",
        "bucket": BucketType.EVENT,
        "thesis": "Government and enterprise pipeline can re-rate on contract wins.",
        "mock_price": Decimal("28.60"),
        "volume": 68500000,
        "moving_average_20": Decimal("27.20"),
        "rsi_14": 64.6,
        "earnings_offset_days": 7,
        "news_summary": "New contract headlines keep traders focused on catalyst timing.",
    },
]


def seed_demo_data(db: Session) -> dict[str, int]:
    existing = db.scalar(select(WatchlistItem.id).limit(1))
    if existing is not None:
        return {
            "seeded_assets": 0,
            "seeded_watchlist_items": 0,
            "seeded_market_snapshots": 0,
            "generated_recommendations": 0,
        }

    watchlist_items: list[WatchlistItem] = []
    market_snapshots: list[MarketSnapshot] = []

    for asset in ASSET_SEEDS:
        watchlist_item = WatchlistItem(
            symbol=asset["symbol"],
            bucket=asset["bucket"],
            thesis=asset["thesis"],
            is_active=True,
        )
        db.add(watchlist_item)
        db.flush()
        watchlist_items.append(watchlist_item)

        earnings_date = date.today() + timedelta(days=asset["earnings_offset_days"])
        snapshot_payload = {
            "symbol": asset["symbol"],
            "mock_price": float(asset["mock_price"]),
            "volume": asset["volume"],
            "moving_average_20": float(asset["moving_average_20"]),
            "rsi_14": asset["rsi_14"],
            "earnings_date": earnings_date.isoformat(),
            "news_summary": asset["news_summary"],
        }
        snapshot = MarketSnapshot(
            symbol=asset["symbol"],
            watchlist_item_id=watchlist_item.id,
            mock_price=asset["mock_price"],
            volume=asset["volume"],
            moving_average_20=asset["moving_average_20"],
            rsi_14=asset["rsi_14"],
            earnings_date=earnings_date,
            news_summary=asset["news_summary"],
            snapshot_payload=snapshot_payload,
        )
        db.add(snapshot)
        db.flush()
        market_snapshots.append(snapshot)

    generated_recommendations = 0
    for watchlist_item, snapshot in zip(watchlist_items, market_snapshots, strict=True):
        if watchlist_item.bucket != BucketType.SWING:
            continue

        above_ma = snapshot.mock_price > snapshot.moving_average_20
        constructive_rsi = 50 <= snapshot.rsi_14 <= 70
        near_earnings = (
            snapshot.earnings_date is not None
            and (snapshot.earnings_date - date.today()).days <= 14
        )
        if not above_ma or not constructive_rsi:
            continue

        rec_type = RecommendationType.SWING_ADD if near_earnings else RecommendationType.SWING_ENTRY
        why_now = "Price is holding above the 20-day moving average with RSI in a constructive swing range."
        if near_earnings:
            why_now += " Earnings are approaching, which can increase attention and volatility."

        recommendation = Recommendation(
            symbol=watchlist_item.symbol,
            bucket=watchlist_item.bucket,
            title=f"{watchlist_item.symbol} swing setup ready for manual review",
            rationale=watchlist_item.thesis or "Swing setup flagged by mock rule engine.",
            recommendation_type=rec_type,
            why_now=why_now,
            risk_notes=(
                "Manual decision required. Gap risk around catalysts and momentum reversals can invalidate the setup."
            ),
            confidence_score=min(
                0.95,
                round(
                    0.55
                    + (0.1 if above_ma else 0.0)
                    + (0.12 if constructive_rsi else 0.0)
                    + (0.08 if near_earnings else 0.0),
                    2,
                ),
            ),
            compliance_status=ComplianceStatus.MANUAL_REVIEW_REQUIRED,
            source="seed_rule_engine",
            watchlist_item_id=watchlist_item.id,
            market_snapshot_id=snapshot.id,
            mock_price=float(snapshot.mock_price),
            market_snapshot=snapshot.snapshot_payload,
        )
        db.add(recommendation)
        db.flush()
        generated_recommendations += 1

    log_event(
        db,
        event_type="seed.completed",
        entity_type="system",
        entity_id=None,
        payload={
            "assets": len(ASSET_SEEDS),
            "watchlist_items": len(watchlist_items),
            "market_snapshots": len(market_snapshots),
            "generated_recommendations": generated_recommendations,
        },
    )
    db.commit()
    return {
        "seeded_assets": len(ASSET_SEEDS),
        "seeded_watchlist_items": len(watchlist_items),
        "seeded_market_snapshots": len(market_snapshots),
        "generated_recommendations": generated_recommendations,
    }
