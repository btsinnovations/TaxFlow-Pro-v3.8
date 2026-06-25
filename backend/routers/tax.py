from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from .. import models, schemas
from ..rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from ..local import settings as local_settings
from .auth import get_current_user

router = APIRouter(prefix="/tax", tags=["tax"])

def _resolve_tenant_id(request: Request, current_user: models.User, tenant_id: str | int | None = None) -> int | None:
    if tenant_id is not None:
        # Frontend may send 'default' in single-user mode; resolve to user's tenant.
        if isinstance(tenant_id, str) and tenant_id.lower() in ("default", "null", ""):
            return resolve_user_tenant_id(current_user)
        try:
            return int(tenant_id)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"Invalid tenant_id: {tenant_id}")
    if local_settings.is_single_user():
        return resolve_user_tenant_id(current_user)
    tenant_id = request.headers.get("x-tenant-id")
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header required")
    return int(tenant_id)


def _wrap_tenant(request: Request, db: Session, current_user: models.User, tenant_id: str | int | None = None):
    if not is_postgres():
        return
    resolved = _resolve_tenant_id(request, current_user, tenant_id)
    if resolved is not None:
        set_tenant_id(db, resolved)


@router.get("/", response_model=list[schemas.CategorizationRuleOut])
def list_tax_rules(
    request: Request,
    tenant_id: str | int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return categorization rules formatted as tax rules."""
    effective_tenant_id = _resolve_tenant_id(request, current_user, tenant_id)
    _wrap_tenant(request, db, current_user, tenant_id)
    rules = db.query(models.CategorizationRule).filter(
        models.CategorizationRule.tenant_id == effective_tenant_id,
        models.CategorizationRule.user_id == current_user.id,
    ).order_by(models.CategorizationRule.priority.desc()).all()
    return rules


@router.patch("/{rule_id}", response_model=schemas.CategorizationRuleOut)
def update_tax_rule(
    request: Request,
    rule_id: int,
    tenant_id: str | int | None = Query(None),
    update: schemas.CategorizationRuleUpdate = ...,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    effective_tenant_id = _resolve_tenant_id(request, current_user, tenant_id)
    _wrap_tenant(request, db, current_user, tenant_id)
    rule = db.query(models.CategorizationRule).filter(
        models.CategorizationRule.id == rule_id,
        models.CategorizationRule.tenant_id == effective_tenant_id,
        models.CategorizationRule.user_id == current_user.id,
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    data = update.model_dump(exclude_unset=True)
    if "gl_account_id" in data:
        account = db.query(models.GLAccount).filter(
            models.GLAccount.id == data["gl_account_id"],
            models.GLAccount.tenant_id == effective_tenant_id,
            models.GLAccount.user_id == current_user.id,
        ).first()
        if not account:
            raise HTTPException(status_code=404, detail="GL account not found")

    for key, value in data.items():
        setattr(rule, key, value)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/summary/{year}")
def tax_summary(request: Request, year: int,
                db: Session = Depends(get_db),
                current_user: models.User = Depends(get_current_user)):
    _wrap_tenant(request, db, current_user)
    prefix = f"{year}-"
    
    income = db.query(func.sum(models.Transaction.amount)).join(models.Statement).filter(
        models.Statement.user_id == current_user.id,
        models.Transaction.amount > 0,
        models.Transaction.date.startswith(prefix)
    ).scalar() or 0.0
    
    expenses = db.query(func.sum(models.Transaction.amount)).join(models.Statement).filter(
        models.Statement.user_id == current_user.id,
        models.Transaction.amount < 0,
        models.Transaction.date.startswith(prefix)
    ).scalar() or 0.0
    
    return {
        "year": year,
        "total_income": round(float(income), 2),
        "total_expenses": round(float(abs(expenses)), 2),
        "net": round(float(income + expenses), 2)
    }
