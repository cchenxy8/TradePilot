from datetime import datetime

from sqlalchemy import Enum, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, TimestampMixin
from backend.app.models.enums import (
    BucketType,
    ComplianceStatus,
    RecommendationAction,
    RecommendationDecisionStatus,
    SetupType,
)


class Recommendation(TimestampMixin, Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    bucket: Mapped[BucketType] = mapped_column(Enum(BucketType), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    recommendation_action: Mapped[RecommendationAction] = mapped_column(
        Enum(RecommendationAction),
        nullable=False,
        index=True,
    )
    setup_type: Mapped[SetupType] = mapped_column(
        Enum(SetupType),
        nullable=False,
        index=True,
    )
    why_now: Mapped[str] = mapped_column(Text, nullable=False)
    risk_notes: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(nullable=False)
    compliance_status: Mapped[ComplianceStatus] = mapped_column(
        Enum(ComplianceStatus),
        nullable=False,
        default=ComplianceStatus.NEEDS_REVIEW,
    )
    decision_status: Mapped[RecommendationDecisionStatus] = mapped_column(
        Enum(RecommendationDecisionStatus),
        default=RecommendationDecisionStatus.PENDING,
        nullable=False,
        index=True,
    )
    watchlist_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("watchlist_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    mock_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    market_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("market_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )
    market_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
