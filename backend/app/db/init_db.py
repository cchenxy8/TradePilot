from backend.app.db.base import Base
from backend.app.db.session import engine
from backend.app.models import audit, journal, market_snapshot, recommendation, watchlist  # noqa: F401
from sqlalchemy import text


def create_db_and_tables() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE market_snapshots ADD COLUMN IF NOT EXISTS latest_price NUMERIC(12, 2)")
        )
        connection.execute(
            text("ALTER TABLE market_snapshots ADD COLUMN IF NOT EXISTS data_provider VARCHAR(50) DEFAULT 'unknown' NOT NULL")
        )
        connection.execute(
            text("ALTER TABLE market_snapshots ADD COLUMN IF NOT EXISTS data_source_type VARCHAR(30) DEFAULT 'unknown' NOT NULL")
        )
        connection.execute(
            text("ALTER TABLE market_snapshots ADD COLUMN IF NOT EXISTS data_delay_note TEXT")
        )
        connection.execute(
            text("ALTER TABLE market_snapshots ADD COLUMN IF NOT EXISTS field_sources JSON")
        )
        connection.execute(
            text("ALTER TABLE market_snapshots ADD COLUMN IF NOT EXISTS is_current BOOLEAN DEFAULT TRUE NOT NULL")
        )
        connection.execute(
            text("ALTER TABLE market_snapshots ADD COLUMN IF NOT EXISTS refreshed_at TIMESTAMPTZ DEFAULT NOW() NOT NULL")
        )
        connection.execute(
            text("ALTER TABLE market_snapshots ALTER COLUMN mock_price DROP NOT NULL")
        )
        connection.execute(
            text("ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS latest_price NUMERIC(12, 2)")
        )
        connection.execute(
            text("ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS rule_results JSON")
        )
        connection.execute(
            text("UPDATE market_snapshots SET latest_price = mock_price WHERE latest_price IS NULL AND mock_price IS NOT NULL")
        )
        connection.execute(
            text("UPDATE recommendations SET latest_price = mock_price WHERE latest_price IS NULL AND mock_price IS NOT NULL")
        )
        connection.execute(
            text(
                """
                UPDATE market_snapshots
                SET data_provider = COALESCE(snapshot_payload ->> 'provider', 'seed-data'),
                    data_source_type = CASE
                        WHEN snapshot_payload ->> 'provider' = 'seed-data' OR mock_price IS NOT NULL THEN 'seeded'
                        WHEN snapshot_payload ->> 'provider' IS NULL THEN 'unknown'
                        ELSE 'provider_delayed'
                    END,
                    data_delay_note = CASE
                        WHEN snapshot_payload ->> 'provider' = 'seed-data' OR mock_price IS NOT NULL THEN 'Seeded demo value, not provider-backed.'
                        WHEN snapshot_payload ->> 'provider' IS NULL THEN 'Unknown source.'
                        ELSE 'Yahoo public market data can be delayed and should not be treated as real-time execution data.'
                    END
                WHERE data_provider = 'unknown'
                """
            )
        )
        connection.execute(
            text(
                """
                UPDATE market_snapshots
                SET data_source_type = 'provider_delayed'
                WHERE data_source_type = 'provider'
                """
            )
        )
        connection.execute(
            text(
                """
                UPDATE market_snapshots
                SET data_delay_note = CASE
                    WHEN data_source_type = 'seeded' THEN 'Seeded demo value, not provider-backed.'
                    WHEN data_source_type = 'provider_delayed' THEN 'Yahoo public market data can be delayed and may not match real-time brokerage quotes.'
                    ELSE COALESCE(data_delay_note, 'Unknown source.')
                END
                WHERE data_delay_note IS NULL
                """
            )
        )
        connection.execute(
            text(
                """
                UPDATE market_snapshots
                SET field_sources = CASE
                    WHEN data_source_type = 'seeded' THEN
                        '{"latest_price":"seed_data","daily_change_pct":"seed_data","volume":"seed_data","earnings_date":"seed_data","avg_volume_20d":"seed_data","moving_average_20":"seed_data","ma50":"seed_data","rsi_14":"seed_data"}'::json
                    WHEN data_source_type = 'provider_delayed' THEN
                        '{"latest_price":"provider_or_provider_fallback","daily_change_pct":"provider_or_derived_from_previous_close","volume":"provider_or_provider_fallback","earnings_date":"provider_if_available","avg_volume_20d":"derived_or_provider_fallback","moving_average_20":"derived_from_provider_chart","ma50":"derived_from_provider_chart","rsi_14":"derived_from_provider_chart"}'::json
                    ELSE '{}'::json
                END
                WHERE field_sources IS NULL
                """
            )
        )
        connection.execute(
            text(
                """
                UPDATE market_snapshots AS snapshot
                SET is_current = snapshot.id = (
                    SELECT active.id
                    FROM market_snapshots AS active
                    WHERE COALESCE(active.watchlist_item_id, -1) = COALESCE(snapshot.watchlist_item_id, -1)
                      AND active.symbol = snapshot.symbol
                      AND active.latest_price IS NOT NULL
                    ORDER BY
                      CASE
                        WHEN active.data_source_type IN ('provider', 'provider_delayed') THEN 1
                        ELSE 0
                      END DESC,
                      active.refreshed_at DESC,
                      active.updated_at DESC,
                      active.id DESC
                    LIMIT 1
                )
                """
            )
        )
