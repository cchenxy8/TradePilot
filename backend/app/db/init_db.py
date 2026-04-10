from backend.app.db.base import Base
from backend.app.db.session import engine
from backend.app.models import audit, journal, market_snapshot, recommendation, watchlist  # noqa: F401


def create_db_and_tables() -> None:
    Base.metadata.create_all(bind=engine)
