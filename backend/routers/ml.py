import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models
from ..rls import is_postgres, set_tenant_id
from .auth import get_current_user, get_current_user_optional
from phase3_pipeline.ml_categorizer import MLCategorizer

logger = logging.getLogger(__name__)

# Module-level ML categorizer instance.  Tolerates a missing model file and
# falls back to the priority/rule-based categorizer internally.
try:
    _ml_categorizer = MLCategorizer()
except Exception as exc:
    logger.exception("Failed to initialize ML categorizer")
    _ml_categorizer = None


def _safe_categorize(description: str, payee: str = "", ml_enabled: bool = False):
    """Return (category, confidence, method) safely, never raising."""
    if _ml_categorizer is None:
        return "Other:Uncategorized", 0.0, "disabled"
    if not ml_enabled:
        cat = (
            _ml_categorizer.priority_cat.categorize(description, payee)
            if _ml_categorizer.priority_cat
            else "Other:Uncategorized"
        )
        return cat, 1.0, "rule"
    try:
        return _ml_categorizer.predict(description, payee)
    except Exception as exc:
        logger.warning("ML prediction failed for %r: %s", description, exc)
        cat = (
            _ml_categorizer.priority_cat.categorize(description, payee)
            if _ml_categorizer.priority_cat
            else "Other:Uncategorized"
        )
        return cat, 1.0, "rule_fallback"


def _get_or_create_firm_settings(db: Session, tenant_id: int) -> models.FirmSettings:
    settings = (
        db.query(models.FirmSettings)
        .filter(models.FirmSettings.tenant_id == tenant_id)
        .first()
    )
    if not settings:
        settings = models.FirmSettings(
            tenant_id=tenant_id,
            firm_name=None,
            firm_address=None,
            firm_phone=None,
            firm_email=None,
            firm_ein=None,
            logo_path=None,
            fiscal_year_end=None,
            timezone="America/New_York",
            date_format="%m/%d/%Y",
            ml_enabled=False,
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def _resolve_tenant_id(
    db: Session,
    current_user: models.User,
    client_id: Optional[int],
    auto_create: bool = False,
) -> int:
    if client_id is not None:
        client = (
            db.query(models.Client)
            .filter(models.Client.id == client_id, models.Client.user_id == current_user.id)
            .first()
        )
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        return client.id

    client = (
        db.query(models.Client)
        .filter(models.Client.user_id == current_user.id)
        .order_by(models.Client.id.asc())
        .first()
    )
    if not client:
        if not auto_create:
            raise HTTPException(status_code=404, detail="No client available for tenant")
        client = models.Client(user_id=current_user.id, name="Default Client")
        db.add(client)
        db.commit()
        db.refresh(client)
    return client.id


router = APIRouter(prefix="/ml", tags=["ml"])


def _wrap_tenant(request: Request, db: Session):
    if is_postgres() and request.headers.get("x-tenant-id"):
        try:
            set_tenant_id(db, int(request.headers.get("x-tenant-id")))
        except ValueError:
            pass


@router.get("/status")
def ml_status(
    request: Request,
    client_id: Optional[int] = Query(None, description="Client ID (tenant)"),
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_current_user_optional),
):
    _wrap_tenant(request, db)
    try:
        tenant_id = _resolve_tenant_id(db, current_user, client_id)
        settings = _get_or_create_firm_settings(db, tenant_id)
        ml_enabled_flag = bool(settings.ml_enabled)
    except (HTTPException, Exception):
        # No client/tenant available yet; return a safe default.
        ml_enabled_flag = False

    model_loaded = _ml_categorizer is not None and _ml_categorizer.model is not None

    return {
        "enabled": ml_enabled_flag and model_loaded,
        "ml_enabled_flag": ml_enabled_flag,
        "model_loaded": model_loaded,
        "model_version": "1.0" if model_loaded else None,
        "accuracy": None,
        "last_trained": None,
        "training_samples": None,
        "message": (
            "ML categorizer is enabled."
            if ml_enabled_flag and model_loaded
            else "ML categorizer is disabled or no trained model was found."
        ),
    }


@router.post("/toggle")
def ml_toggle(
    request: Request,
    client_id: Optional[int] = Query(None, description="Client ID (tenant)"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db)
    tenant_id = _resolve_tenant_id(db, current_user, client_id, auto_create=True)
    settings = _get_or_create_firm_settings(db, tenant_id)

    settings.ml_enabled = not bool(settings.ml_enabled)
    db.commit()
    db.refresh(settings)

    return {
        "enabled": bool(settings.ml_enabled),
        "message": f"ML categorizer {'enabled' if settings.ml_enabled else 'disabled'}.",
    }


@router.post("/categorize/{statement_id}")
def categorize_statement(
    request: Request,
    statement_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db)
    statement = db.query(models.Statement).filter(
        models.Statement.id == statement_id,
        models.Statement.user_id == current_user.id
    ).first()
    if not statement:
        raise HTTPException(status_code=404, detail="Statement not found")

    settings = _get_or_create_firm_settings(db, statement.tenant_id)

    transactions = db.query(models.Transaction).filter(
        models.Transaction.statement_id == statement_id,
        models.Transaction.tenant_id == statement.tenant_id
    ).all()

    if _ml_categorizer is None and settings.ml_enabled:
        raise HTTPException(
            status_code=503,
            detail="ML categorizer could not be loaded. Please train a model or disable ML.",
        )

    updated = 0
    method_counts = {"ml": 0, "rule": 0, "rule_fallback": 0, "disabled": 0}
    for tx in transactions:
        category, confidence, method = _safe_categorize(
            tx.description or "", "", ml_enabled=settings.ml_enabled
        )
        method_counts[method] = method_counts.get(method, 0) + 1
        if tx.category != category:
            tx.category = category
            updated += 1
    db.commit()

    return {
        "statement_id": statement_id,
        "transactions_processed": len(transactions),
        "categories_updated": updated,
        "categories": list(set(t.category for t in transactions)),
        "method_counts": method_counts,
    }
