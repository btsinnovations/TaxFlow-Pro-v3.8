"""
Dashboard statistics endpoint.
"""

from fastapi import APIRouter
from api_models import DashboardStats, AuditEventOut
from api_utils import get_db

router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
async def get_stats():
    db = get_db()
    clients = db.get("clients", {})
    processed = db.get("processed_files", {})
    audit = db.get("audit_log", [])

    pass_count = sum(1 for p in processed.values() if p.get("reconciliation") == "PASS")
    total_reconciled = len([p for p in processed.values() if p.get("reconciliation")])
    pass_rate = (pass_count / total_reconciled * 100) if total_reconciled else 0.0

    recent = []
    for event in audit[:5]:
        recent.append(AuditEventOut(
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

    return DashboardStats(
        total_clients=len(clients),
        total_statements_processed=len(processed),
        total_transactions=sum(p.get("transaction_count", 0) for p in processed.values()),
        avg_processing_time_ms=1500,
        reconciliation_pass_rate=pass_rate,
        ml_model_accuracy=None,
        active_parsers=["Cash App", "TD Bank", "EdFed", "Chime", "Generic"],
        recent_activity=recent,
    )
