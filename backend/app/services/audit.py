from sqlalchemy.orm import Session

from backend.app.models.audit import AuditLog


def log_event(
    db: Session,
    *,
    event_type: str,
    entity_type: str,
    entity_id: int | None,
    payload: dict | None = None,
) -> AuditLog:
    audit_log = AuditLog(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
    )
    db.add(audit_log)
    return audit_log
