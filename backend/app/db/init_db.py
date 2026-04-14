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
            text("ALTER TABLE market_snapshots ALTER COLUMN mock_price DROP NOT NULL")
        )
        connection.execute(
            text("ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS latest_price NUMERIC(12, 2)")
        )
        connection.execute(
            text("UPDATE market_snapshots SET latest_price = mock_price WHERE latest_price IS NULL AND mock_price IS NOT NULL")
        )
        connection.execute(
            text("UPDATE recommendations SET latest_price = mock_price WHERE latest_price IS NULL AND mock_price IS NOT NULL")
        )
