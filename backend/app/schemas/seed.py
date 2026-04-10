from pydantic import BaseModel


class SeedResult(BaseModel):
    seeded_assets: int
    seeded_watchlist_items: int
    seeded_market_snapshots: int
    generated_recommendations: int
