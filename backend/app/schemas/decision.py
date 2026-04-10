from datetime import datetime

from pydantic import Field

from backend.app.models.enums import RecommendationStatus
from backend.app.schemas.common import ORMModel


class RecommendationDecisionRequest(ORMModel):
    action: RecommendationStatus = Field(
        description="Decision to apply to a recommendation",
    )
    reason: str | None = None
    decided_at: datetime = Field(default_factory=datetime.utcnow)
