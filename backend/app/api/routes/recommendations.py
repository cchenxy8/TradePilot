from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.enums import BucketType, RecommendationStatus
from backend.app.models.recommendation import Recommendation
from backend.app.schemas.decision import RecommendationDecisionRequest
from backend.app.schemas.recommendation import RecommendationCreate, RecommendationRead
from backend.app.services.audit import log_event
from backend.app.services.mock_market_data import get_mock_quote
from backend.app.services.recommendation_engine import generate_swing_recommendations


router = APIRouter()


@router.get("", response_model=list[RecommendationRead])
def list_recommendations(
    status_filter: RecommendationStatus | None = Query(default=None, alias="status"),
    bucket: BucketType | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Recommendation]:
    query = select(Recommendation).order_by(Recommendation.generated_at.desc())
    if status_filter is not None:
        query = query.where(Recommendation.status == status_filter)
    if bucket is not None:
        query = query.where(Recommendation.bucket == bucket)
    return list(db.scalars(query))


@router.post("", response_model=RecommendationRead, status_code=status.HTTP_201_CREATED)
def create_recommendation(
    payload: RecommendationCreate,
    db: Session = Depends(get_db),
) -> Recommendation:
    quote = get_mock_quote(payload.symbol)
    recommendation = Recommendation(
        **payload.model_dump(),
        mock_price=quote.price,
        market_snapshot=quote.model_dump(mode="json"),
    )
    db.add(recommendation)
    db.flush()
    log_event(
        db,
        event_type="recommendation.created",
        entity_type="recommendation",
        entity_id=recommendation.id,
        payload={
            **payload.model_dump(mode="json"),
            "market_snapshot": quote.model_dump(mode="json"),
        },
    )
    db.commit()
    db.refresh(recommendation)
    return recommendation


@router.post("/generate/swing", response_model=list[RecommendationRead], status_code=status.HTTP_201_CREATED)
def generate_swing_queue(db: Session = Depends(get_db)) -> list[Recommendation]:
    return generate_swing_recommendations(db)


@router.post(
    "/{recommendation_id}/decision",
    response_model=RecommendationRead,
    status_code=status.HTTP_200_OK,
)
def decide_recommendation(
    recommendation_id: int,
    payload: RecommendationDecisionRequest,
    db: Session = Depends(get_db),
) -> Recommendation:
    recommendation = db.get(Recommendation, recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    if payload.action == RecommendationStatus.PENDING:
        raise HTTPException(status_code=400, detail="Decision action must not be pending")

    recommendation.status = payload.action
    recommendation.decision_reason = payload.reason
    recommendation.decided_at = payload.decided_at

    db.flush()
    log_event(
        db,
        event_type=f"recommendation.{payload.action.value}",
        entity_type="recommendation",
        entity_id=recommendation.id,
        payload=payload.model_dump(mode="json"),
    )
    db.commit()
    db.refresh(recommendation)
    return recommendation
