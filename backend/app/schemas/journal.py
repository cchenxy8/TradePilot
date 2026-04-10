from datetime import datetime

from backend.app.schemas.common import ORMModel, TimestampedRead


class JournalEntryCreate(ORMModel):
    title: str
    content: str
    symbol: str | None = None
    recommendation_id: int | None = None


class JournalEntryRead(TimestampedRead):
    id: int
    title: str
    content: str
    symbol: str | None
    recommendation_id: int | None


class AuditLogRead(ORMModel):
    id: int
    event_type: str
    entity_type: str
    entity_id: int | None
    payload: dict | None
    created_at: datetime
