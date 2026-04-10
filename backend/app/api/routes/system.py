from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.market_snapshot import MarketSnapshot
from backend.app.schemas.market_snapshot import MarketSnapshotRead
from backend.app.schemas.seed import SeedResult
from backend.app.services.seed_data import seed_demo_data


router = APIRouter()


@router.post("/seed", response_model=SeedResult, status_code=status.HTTP_201_CREATED)
def seed_system(db: Session = Depends(get_db)) -> SeedResult:
    result = seed_demo_data(db)
    return SeedResult(**result)


@router.get("/market-snapshots", response_model=list[MarketSnapshotRead])
def list_market_snapshots(db: Session = Depends(get_db)) -> list[MarketSnapshot]:
    return list(
        db.scalars(
            select(MarketSnapshot).order_by(
                MarketSnapshot.captured_at.desc(),
                MarketSnapshot.symbol.asc(),
            )
        )
    )
