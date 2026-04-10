from pydantic import BaseModel

from backend.app.models.enums import BucketType
from backend.app.schemas.common import TimestampedRead


class WatchlistItemCreate(BaseModel):
    symbol: str
    bucket: BucketType
    thesis: str | None = None
    is_active: bool = True


class WatchlistItemUpdate(BaseModel):
    bucket: BucketType | None = None
    thesis: str | None = None
    is_active: bool | None = None


class WatchlistItemRead(TimestampedRead):
    id: int
    symbol: str
    bucket: BucketType
    thesis: str | None
    is_active: bool
