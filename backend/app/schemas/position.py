from datetime import datetime

from pydantic import BaseModel, Field

from backend.app.models.enums import PositionAction, PositionSourceType
from backend.app.schemas.common import TimestampedRead


class PortfolioPositionCreate(BaseModel):
    account_id: str | None = None
    source_type: PositionSourceType = PositionSourceType.MANUAL_ENTRY
    external_position_id: str | None = None
    last_synced_at: datetime | None = None
    symbol: str
    shares: float = Field(gt=0)
    average_cost: float | None = None
    current_price: float | None = None
    unrealized_pnl: float | None = None
    portfolio_weight: float | None = None
    thesis: str | None = None
    notes: str | None = None
    recommended_action: PositionAction = PositionAction.REVIEW


class PortfolioPositionRead(TimestampedRead):
    id: int
    account_id: str | None
    source_type: PositionSourceType
    external_position_id: str | None
    last_synced_at: datetime | None
    symbol: str
    shares: float
    average_cost: float | None
    current_price: float | None
    unrealized_pnl: float | None
    portfolio_weight: float | None
    thesis: str | None
    notes: str | None
    recommended_action: PositionAction


class PositionCsvImportRequest(BaseModel):
    csv_text: str
    account_id: str | None = None
    source_type: PositionSourceType = PositionSourceType.CSV_IMPORT
    last_synced_at: datetime | None = None


class PositionCsvImportResult(BaseModel):
    imported_count: int
    skipped_count: int
    positions: list[PortfolioPositionRead]
    errors: list[str]


class BrokerReadonlySyncRequest(BaseModel):
    account_id: str
    positions: list[PortfolioPositionCreate]
    last_synced_at: datetime | None = None
