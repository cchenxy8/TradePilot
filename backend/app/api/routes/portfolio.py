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
    PositionCsvPreviewRequest,
    PositionCsvPreviewResult,
)
from backend.app.services.audit import log_event
from backend.app.services.portfolio_analysis import position_read_payload


router = APIRouter()

POSITION_IMPORT_FIELDS = [
    "symbol",
    "shares",
    "average_cost",
    "current_price",
    "portfolio_weight",
    "thesis",
    "notes",
]

POSITION_COLUMN_ALIASES = {
    "symbol": {"symbol", "ticker"},
    "shares": {"shares", "share", "qty", "quantity"},
    "average_cost": {"average_cost", "avg_cost", "avg_price", "cost_basis", "cost"},
    "current_price": {"current_price", "market_price", "last_price", "price"},
    "portfolio_weight": {"portfolio_weight", "weight", "allocation", "portfolio_pct"},
    "thesis": {"thesis", "investment_thesis"},
    "notes": {"notes", "note", "comments", "comment"},
}


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


def _normalize_header(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _suggest_column_mapping(headers: list[str]) -> dict[str, str | None]:
    normalized_headers = {_normalize_header(header): header for header in headers}
    mapping: dict[str, str | None] = {}
    for field in POSITION_IMPORT_FIELDS:
        mapping[field] = None
        for alias in POSITION_COLUMN_ALIASES[field]:
            if alias in normalized_headers:
                mapping[field] = normalized_headers[alias]
                break
    return mapping


def _mapped_value(row: dict[str, str], mapping: dict[str, str | None], field: str) -> str | None:
    header = mapping.get(field)
    if header is None or header == "":
        return None
    return row.get(header)


def _csv_rows(csv_text: str) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(StringIO(csv_text.strip()))
    return list(reader.fieldnames or []), list(reader)


def _preview_row(row_number: int, row: dict[str, str], mapping: dict[str, str | None]) -> dict:
    symbol = (_mapped_value(row, mapping, "symbol") or "").strip().upper()
    shares = _decimal_or_none(_mapped_value(row, mapping, "shares"))
    average_cost = _decimal_or_none(_mapped_value(row, mapping, "average_cost"))
    current_price = _decimal_or_none(_mapped_value(row, mapping, "current_price"))
    portfolio_weight = _float_or_none(_mapped_value(row, mapping, "portfolio_weight"))
    thesis = _mapped_value(row, mapping, "thesis")
    notes = _mapped_value(row, mapping, "notes")
    errors = []
    if symbol == "":
        errors.append("Missing symbol.")
    if shares is None:
        errors.append("Missing or invalid shares.")
    elif shares <= 0:
        errors.append("Shares must be greater than zero.")

    return {
        "row_number": row_number,
        "values": {
            "symbol": symbol or None,
            "shares": float(shares) if shares is not None else None,
            "average_cost": float(average_cost) if average_cost is not None else None,
            "current_price": float(current_price) if current_price is not None else None,
            "portfolio_weight": portfolio_weight,
            "thesis": thesis,
            "notes": notes,
        },
        "errors": errors,
    }


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
) -> list[dict]:
    query = select(PortfolioPosition).order_by(PortfolioPosition.symbol.asc())
    if account_id is not None:
        query = query.where(PortfolioPosition.account_id == account_id)
    if source_type is not None:
        query = query.where(PortfolioPosition.source_type == source_type)
    return [position_read_payload(db, position) for position in db.scalars(query)]


@router.post("/positions", response_model=PortfolioPositionRead, status_code=status.HTTP_201_CREATED)
def create_position(
    payload: PortfolioPositionCreate,
    db: Session = Depends(get_db),
) -> dict:
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
    return position_read_payload(db, position)


@router.post("/positions/import-csv", response_model=PositionCsvImportResult, status_code=status.HTTP_201_CREATED)
def import_positions_csv(
    payload: PositionCsvImportRequest,
    db: Session = Depends(get_db),
) -> PositionCsvImportResult:
    headers, rows = _csv_rows(payload.csv_text)
    mapping = payload.column_mapping or _suggest_column_mapping(headers)
    positions: list[PortfolioPosition] = []
    errors: list[str] = []
    skipped_count = 0

    for row_number, row in enumerate(rows, start=2):
        preview = _preview_row(row_number, row, mapping)
        if preview["errors"]:
            skipped_count += 1
            errors.extend(f"Row {row_number}: {error}" for error in preview["errors"])
            continue
        values = preview["values"]

        position = PortfolioPosition(
            account_id=payload.account_id,
            source_type=payload.source_type,
            external_position_id=None,
            last_synced_at=payload.last_synced_at,
            symbol=str(values["symbol"]),
            shares=Decimal(str(values["shares"])),
            average_cost=Decimal(str(values["average_cost"])) if values["average_cost"] is not None else None,
            current_price=Decimal(str(values["current_price"])) if values["current_price"] is not None else None,
            unrealized_pnl=None,
            portfolio_weight=values["portfolio_weight"],
            thesis=values["thesis"],
            notes=values["notes"],
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
        positions=[position_read_payload(db, position) for position in positions],
        errors=errors,
    )


@router.post("/positions/import-csv/preview", response_model=PositionCsvPreviewResult)
def preview_positions_csv(payload: PositionCsvPreviewRequest) -> PositionCsvPreviewResult:
    headers, rows = _csv_rows(payload.csv_text)
    suggested_mapping = _suggest_column_mapping(headers)
    mapping = payload.column_mapping or suggested_mapping
    errors = []
    if not headers:
        errors.append("CSV file has no header row.")
    if mapping.get("symbol") is None:
        errors.append("Map a column to symbol before import.")
    if mapping.get("shares") is None:
        errors.append("Map a column to shares before import.")

    preview_rows = [_preview_row(row_number, row, mapping) for row_number, row in enumerate(rows, start=2)]
    row_error_count = sum(1 for row in preview_rows if row["errors"])
    return PositionCsvPreviewResult(
        headers=headers,
        suggested_mapping=suggested_mapping,
        rows=preview_rows[:25],
        valid_count=max(len(rows) - row_error_count, 0),
        error_count=row_error_count + len(errors),
        errors=errors,
    )


@router.post("/positions/broker-readonly/sync", response_model=list[PortfolioPositionRead])
def sync_broker_readonly_positions(
    payload: BrokerReadonlySyncRequest,
    db: Session = Depends(get_db),
) -> list[dict]:
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
    return [position_read_payload(db, position) for position in synced]
