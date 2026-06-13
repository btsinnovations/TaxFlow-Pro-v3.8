"""
Audit trail endpoints.
"""

from fastapi import APIRouter, Query
from typing import List, Optional
from api_models import AuditEventOut
from api_utils import get_db

router = APIRouter()


@router.get("/", response_model=List[AuditEventOut])
async def list_audit(
    severity: Optional[str] = Query(None, description="Filter by severity: INFO, WARNING, ERROR, CRITICAL"),
    event_type: Optional[str] = Query(None),
    client_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    db = get_db()
    events = db.get("audit_log", [])

    if severity:
        events = [e for e in events if e.get("severity") == severity.upper()]
    if event_type:
        events = [e for e in events if event_type.lower() in e.get("event_type", "").lower()]
    if client_id:
        events = [e for e in events if e.get("client_id") == client_id]

    total = len(events)
    events = events[offset:offset + limit]

    result = []
    for event in events:
        result.append(AuditEventOut(
            id=event.get("id", ""),
            timestamp=event.get("timestamp", ""),
            severity=event.get("severity", "INFO"),
            event_type=event.get("event_type", ""),
            client_id=event.get("client_id"),
            description=event.get("description", ""),
            user=event.get("user", "system"),
            session_id=event.get("session_id", ""),
            details=event.get("details"),
        ))

    return result


@router.get("/stats")
async def audit_stats():
    db = get_db()
    events = db.get("audit_log", [])
    return {
        "total_events": len(events),
        "by_severity": {
            "INFO": sum(1 for e in events if e.get("severity") == "INFO"),
            "WARNING": sum(1 for e in events if e.get("severity") == "WARNING"),
            "ERROR": sum(1 for e in events if e.get("severity") == "ERROR"),
            "CRITICAL": sum(1 for e in events if e.get("severity") == "CRITICAL"),
        },
    }
