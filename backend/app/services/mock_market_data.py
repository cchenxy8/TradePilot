from decimal import Decimal
from datetime import date, timedelta

from pydantic import BaseModel


class MockQuote(BaseModel):
    symbol: str
    price: Decimal
    volume: int
    moving_average_20: Decimal
    rsi_14: float
    earnings_date: date
    news_summary: str
    provider: str = "mock-feed"


def get_mock_quote(symbol: str) -> MockQuote:
    normalized = symbol.upper()
    seed = sum(ord(char) for char in normalized)
    base_price = Decimal("25.00") + Decimal(seed % 200)
    volume = 100_000 + (seed * 137) % 2_000_000
    moving_average_20 = base_price - Decimal((seed % 9) - 4)
    rsi_14 = round(42 + (seed % 28), 1)
    earnings_date = date.today() + timedelta(days=(seed % 30) + 3)
    news_summary = f"{normalized} mock headline flow remains neutral-to-constructive for manual research review."
    return MockQuote(
        symbol=normalized,
        price=base_price,
        volume=volume,
        moving_average_20=moving_average_20,
        rsi_14=rsi_14,
        earnings_date=earnings_date,
        news_summary=news_summary,
    )
