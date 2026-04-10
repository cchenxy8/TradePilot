from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.enums import BucketType
from backend.app.models.watchlist import WatchlistItem
from backend.app.schemas.watchlist import (
    WatchlistItemCreate,
    WatchlistItemRead,
    WatchlistItemUpdate,
)
from backend.app.services.audit import log_event


router = APIRouter()


@router.get("", response_model=list[WatchlistItemRead])
def list_watchlist_items(
    bucket: BucketType | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[WatchlistItem]:
    query = select(WatchlistItem).order_by(WatchlistItem.created_at.desc())
    if bucket is not None:
        query = query.where(WatchlistItem.bucket == bucket)
    return list(db.scalars(query))


@router.post("", response_model=WatchlistItemRead, status_code=status.HTTP_201_CREATED)
def create_watchlist_item(
    payload: WatchlistItemCreate,
    db: Session = Depends(get_db),
) -> WatchlistItem:
    item = WatchlistItem(**payload.model_dump())
    db.add(item)
    db.flush()
    log_event(
        db,
        event_type="watchlist.created",
        entity_type="watchlist_item",
        entity_id=item.id,
        payload=payload.model_dump(mode="json"),
    )
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{item_id}", response_model=WatchlistItemRead)
def update_watchlist_item(
    item_id: int,
    payload: WatchlistItemUpdate,
    db: Session = Depends(get_db),
) -> WatchlistItem:
    item = db.get(WatchlistItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Watchlist item not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)

    db.flush()
    log_event(
        db,
        event_type="watchlist.updated",
        entity_type="watchlist_item",
        entity_id=item.id,
        payload=payload.model_dump(mode="json", exclude_unset=True),
    )
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist_item(
    item_id: int,
    db: Session = Depends(get_db),
) -> None:
    item = db.get(WatchlistItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Watchlist item not found")

    log_event(
        db,
        event_type="watchlist.deleted",
        entity_type="watchlist_item",
        entity_id=item.id,
        payload={"symbol": item.symbol},
    )
    db.delete(item)
    db.commit()
