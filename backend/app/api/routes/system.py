from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.market_snapshot import MarketSnapshot
from backend.app.schemas.market_snapshot import MarketSnapshotRead
from backend.app.schemas.seed import SeedResult
from backend.app.services.market_data import (
    MarketDataRefreshError,
    list_active_market_snapshots,
    refresh_watchlist_market_snapshots,
)
from backend.app.services.seed_data import seed_demo_data


router = APIRouter()


@router.post("/seed", response_model=SeedResult, status_code=status.HTTP_201_CREATED)
def seed_system(db: Session = Depends(get_db)) -> SeedResult:
    result = seed_demo_data(db)
    return SeedResult(**result)


@router.get("/market-snapshots", response_model=list[MarketSnapshotRead])
def list_market_snapshots(
    current_only: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> list[MarketSnapshot]:
    if current_only:
        return list_active_market_snapshots(db)
    query = select(MarketSnapshot)
    return list(
        db.scalars(
            query.order_by(
                MarketSnapshot.refreshed_at.desc(),
                MarketSnapshot.captured_at.desc(),
                MarketSnapshot.symbol.asc(),
            )
        )
    )


@router.post(
    "/market-snapshots/refresh",
    response_model=list[MarketSnapshotRead],
    status_code=status.HTTP_201_CREATED,
)
def refresh_market_snapshots(db: Session = Depends(get_db)) -> list[MarketSnapshot]:
    try:
        return refresh_watchlist_market_snapshots(db)
    except MarketDataRefreshError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": str(error),
                "failures": error.failures,
            },
        ) from error
