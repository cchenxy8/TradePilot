from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.audit import AuditLog
from backend.app.models.journal import JournalEntry
from backend.app.models.recommendation import Recommendation
from backend.app.schemas.journal import AuditLogRead, JournalEntryCreate, JournalEntryRead
from backend.app.services.audit import log_event


router = APIRouter()


@router.get("", response_model=list[JournalEntryRead])
def list_journal_entries(db: Session = Depends(get_db)) -> list[JournalEntry]:
    query = select(JournalEntry).order_by(JournalEntry.created_at.desc())
    return list(db.scalars(query))


@router.post("", response_model=JournalEntryRead, status_code=status.HTTP_201_CREATED)
def create_journal_entry(
    payload: JournalEntryCreate,
    db: Session = Depends(get_db),
) -> JournalEntry:
    if payload.recommendation_id is not None:
        recommendation = db.get(Recommendation, payload.recommendation_id)
        if recommendation is None:
            raise HTTPException(status_code=404, detail="Recommendation not found")

    entry = JournalEntry(**payload.model_dump())
    db.add(entry)
    db.flush()
    log_event(
        db,
        event_type="journal.created",
        entity_type="journal_entry",
        entity_id=entry.id,
        payload=payload.model_dump(mode="json"),
    )
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/audit", response_model=list[AuditLogRead])
def list_audit_logs(db: Session = Depends(get_db)) -> list[AuditLog]:
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    return list(db.scalars(query))
