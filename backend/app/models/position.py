from datetime import datetime
from decimal import Decimal

from sqlalchemy import Enum, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin
from backend.app.models.enums import PositionAction, PositionSourceType


class PortfolioPosition(TimestampMixin, Base):
    __tablename__ = "portfolio_positions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    account_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    source_type: Mapped[PositionSourceType] = mapped_column(
        Enum(PositionSourceType),
        default=PositionSourceType.MANUAL_ENTRY,
        nullable=False,
        index=True,
    )
    external_position_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(nullable=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    shares: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    average_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    unrealized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    portfolio_weight: Mapped[float | None] = mapped_column(nullable=True)
    thesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[PositionAction] = mapped_column(
        Enum(PositionAction),
        default=PositionAction.REVIEW,
        nullable=False,
        index=True,
    )
