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
    assessment_rationale: str | None = None
    assessment_summary: str | None = None
    pnl_pct: float | None = None
    market_snapshot: dict | None = None
    read_only_note: str = "Read-only position analysis. TradePilot does not place orders."


class PositionCsvImportRequest(BaseModel):
    csv_text: str
    account_id: str | None = None
    source_type: PositionSourceType = PositionSourceType.CSV_IMPORT
    last_synced_at: datetime | None = None
    column_mapping: dict[str, str | None] | None = None


class PositionCsvImportResult(BaseModel):
    imported_count: int
    skipped_count: int
    positions: list[PortfolioPositionRead]
    errors: list[str]


class PositionCsvPreviewRequest(BaseModel):
    csv_text: str
    column_mapping: dict[str, str | None] | None = None


class PositionCsvPreviewRow(BaseModel):
    row_number: int
    values: dict[str, str | float | None]
    errors: list[str]


class PositionCsvPreviewResult(BaseModel):
    headers: list[str]
    suggested_mapping: dict[str, str | None]
    rows: list[PositionCsvPreviewRow]
    valid_count: int
    error_count: int
    errors: list[str]


class BrokerReadonlySyncRequest(BaseModel):
    account_id: str
    positions: list[PortfolioPositionCreate]
    last_synced_at: datetime | None = None
