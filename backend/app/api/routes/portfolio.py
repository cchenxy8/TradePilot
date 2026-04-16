import csv
from decimal import Decimal, InvalidOperation
from io import StringIO

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.enums import PositionAction, PositionSourceType
from backend.app.models.position import PortfolioPosition
from backend.app.schemas.position import (
    BrokerReadonlySyncRequest,
    PortfolioPositionCreate,
    PortfolioPositionRead,
    PositionCsvImportRequest,
    PositionCsvImportResult,
)
from backend.app.services.audit import log_event


router = APIRouter()


def _decimal_or_none(value: str | None) -> Decimal | None:
    if value is None or value.strip() == "":
        return None
    try:
        return Decimal(value.strip().replace("$", "").replace(",", ""))
    except InvalidOperation:
        return None


def _float_or_none(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    try:
        return float(value.strip().replace("%", "")) / (100 if "%" in value else 1)
    except ValueError:
        return None


def _row_value(row: dict[str, str], *names: str) -> str | None:
    normalized = {key.strip().lower().replace(" ", "_"): value for key, value in row.items()}
    for name in names:
        value = normalized.get(name)
        if value is not None:
            return value
    return None


@router.get("/positions", response_model=list[PortfolioPositionRead])
def list_positions(
    account_id: str | None = Query(default=None),
    source_type: PositionSourceType | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[PortfolioPosition]:
    query = select(PortfolioPosition).order_by(PortfolioPosition.symbol.asc())
    if account_id is not None:
        query = query.where(PortfolioPosition.account_id == account_id)
    if source_type is not None:
        query = query.where(PortfolioPosition.source_type == source_type)
    return list(db.scalars(query))


@router.post("/positions", response_model=PortfolioPositionRead, status_code=status.HTTP_201_CREATED)
def create_position(
    payload: PortfolioPositionCreate,
    db: Session = Depends(get_db),
) -> PortfolioPosition:
    position = PortfolioPosition(**payload.model_dump())
    position.symbol = position.symbol.upper()
    db.add(position)
    db.flush()
    log_event(
        db,
        event_type="portfolio.position.created",
        entity_type="portfolio_position",
        entity_id=position.id,
        payload=payload.model_dump(mode="json"),
    )
    db.commit()
    db.refresh(position)
    return position


@router.post("/positions/import-csv", response_model=PositionCsvImportResult, status_code=status.HTTP_201_CREATED)
def import_positions_csv(
    payload: PositionCsvImportRequest,
    db: Session = Depends(get_db),
) -> PositionCsvImportResult:
    reader = csv.DictReader(StringIO(payload.csv_text.strip()))
    positions: list[PortfolioPosition] = []
    errors: list[str] = []
    skipped_count = 0

    for row_number, row in enumerate(reader, start=2):
        symbol = _row_value(row, "symbol", "ticker")
        shares = _decimal_or_none(_row_value(row, "shares", "quantity", "qty"))
        if symbol is None or symbol.strip() == "" or shares is None:
            skipped_count += 1
            errors.append(f"Row {row_number}: missing symbol or shares.")
            continue

        position = PortfolioPosition(
            account_id=_row_value(row, "account_id") or payload.account_id,
            source_type=payload.source_type,
            external_position_id=_row_value(row, "external_position_id", "position_id"),
            last_synced_at=payload.last_synced_at,
            symbol=symbol.strip().upper(),
            shares=shares,
            average_cost=_decimal_or_none(_row_value(row, "average_cost", "avg_cost", "cost_basis")),
            current_price=_decimal_or_none(_row_value(row, "current_price", "last_price", "market_price")),
            unrealized_pnl=_decimal_or_none(_row_value(row, "unrealized_pnl", "unrealized_gain_loss", "pnl")),
            portfolio_weight=_float_or_none(_row_value(row, "portfolio_weight", "weight")),
            thesis=_row_value(row, "thesis"),
            notes=_row_value(row, "notes"),
            recommended_action=PositionAction.REVIEW,
        )
        db.add(position)
        positions.append(position)

    db.flush()
    for position in positions:
        log_event(
            db,
            event_type="portfolio.position.imported",
            entity_type="portfolio_position",
            entity_id=position.id,
            payload={
                "symbol": position.symbol,
                "source_type": position.source_type.value,
                "account_id": position.account_id,
            },
        )
    db.commit()
    for position in positions:
        db.refresh(position)

    return PositionCsvImportResult(
        imported_count=len(positions),
        skipped_count=skipped_count,
        positions=positions,
        errors=errors,
    )


@router.post("/positions/broker-readonly/sync", response_model=list[PortfolioPositionRead])
def sync_broker_readonly_positions(
    payload: BrokerReadonlySyncRequest,
    db: Session = Depends(get_db),
) -> list[PortfolioPosition]:
    synced: list[PortfolioPosition] = []
    for item in payload.positions:
        external_position_id = item.external_position_id or item.symbol.upper()
        position = db.scalar(
            select(PortfolioPosition)
            .where(
                PortfolioPosition.account_id == payload.account_id,
                PortfolioPosition.source_type == PositionSourceType.BROKER_READONLY,
                PortfolioPosition.external_position_id == external_position_id,
            )
            .limit(1)
        )
        values = item.model_dump()
        values.update(
            {
                "account_id": payload.account_id,
                "source_type": PositionSourceType.BROKER_READONLY,
                "external_position_id": external_position_id,
                "last_synced_at": payload.last_synced_at,
                "symbol": item.symbol.upper(),
                "recommended_action": PositionAction.REVIEW,
            }
        )
        if position is None:
            position = PortfolioPosition(**values)
            db.add(position)
        else:
            for field, value in values.items():
                setattr(position, field, value)
        synced.append(position)

    db.flush()
    for position in synced:
        log_event(
            db,
            event_type="portfolio.position.broker_readonly_synced",
            entity_type="portfolio_position",
            entity_id=position.id,
            payload={
                "symbol": position.symbol,
                "account_id": position.account_id,
                "external_position_id": position.external_position_id,
            },
        )
    db.commit()
    for position in synced:
        db.refresh(position)
    return synced
