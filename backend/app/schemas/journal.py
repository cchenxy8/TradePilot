from datetime import datetime

from backend.app.models.enums import BucketType
from backend.app.schemas.common import ORMModel, TimestampedRead


class JournalEntryCreate(ORMModel):
    title: str
    content: str
    symbol: str | None = None
    bucket: BucketType | None = None
    recommendation_id: int | None = None
    planned_entry: float | None = None
    planned_exit: float | None = None
    stop_loss: float | None = None
    position_size_pct: float | None = None
    outcome_note: str | None = None


class JournalEntryRead(TimestampedRead):
    id: int
    title: str
    content: str
    symbol: str | None
    bucket: BucketType | None
    recommendation_id: int | None
    planned_entry: float | None
    planned_exit: float | None
    stop_loss: float | None
    position_size_pct: float | None
    outcome_note: str | None


class AuditLogRead(ORMModel):
    id: int
    event_type: str
    entity_type: str
    entity_id: int | None
    payload: dict | None
    created_at: datetime
