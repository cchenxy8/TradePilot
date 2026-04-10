from sqlalchemy import Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin
from backend.app.models.enums import BucketType


class JournalEntry(TimestampMixin, Base):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    bucket: Mapped[BucketType | None] = mapped_column(Enum(BucketType), nullable=True, index=True)
    recommendation_id: Mapped[int | None] = mapped_column(
        ForeignKey("recommendations.id", ondelete="SET NULL"),
        nullable=True,
    )
    planned_entry: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    planned_exit: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    position_size_pct: Mapped[float | None] = mapped_column(nullable=True)
    outcome_note: Mapped[str | None] = mapped_column(Text, nullable=True)
