from decimal import Decimal

from pydantic import BaseModel


class MockQuote(BaseModel):
    symbol: str
    price: Decimal
    day_change_pct: float
    volume: int
    provider: str = "mock-feed"


def get_mock_quote(symbol: str) -> MockQuote:
    normalized = symbol.upper()
    seed = sum(ord(char) for char in normalized)
    base_price = Decimal("25.00") + Decimal(seed % 200)
    day_change_pct = round(((seed % 11) - 5) * 0.6, 2)
    volume = 100_000 + (seed * 137) % 2_000_000
    return MockQuote(
        symbol=normalized,
        price=base_price,
        day_change_pct=day_change_pct,
        volume=volume,
    )

