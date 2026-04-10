from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin


class JournalEntry(TimestampMixin, Base):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    recommendation_id: Mapped[int | None] = mapped_column(
        ForeignKey("recommendations.id", ondelete="SET NULL"),
        nullable=True,
    )
