"""Recurring / scheduled transaction rule API endpoints for TaxFlow Pro v3.11."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.accounting.recurring import (
    create_rule,
    delete_rule,
    get_rule,
    list_rules,
    materialize_rule,
    update_rule,
)
from backend.audit import record, AuditAction, AuditResource
from backend.database import get_db
from backend.routers.auth import get_current_user
from backend import models, schemas
from backend.rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from backend.local import settings as local_settings

router = APIRouter(prefix="/recurring", tags=["recurring"])


def _wrap_tenant(request: Request, db: Session, current_user: models.User) -> int:
    """Resolve tenant_id for the request and apply Postgres RLS if needed."""
    if not is_postgres():
        return resolve_user_tenant_id(current_user)
    if local_settings.is_single_user():
        tenant_id = resolve_user_tenant_id(current_user)
        set_tenant_id(db, tenant_id)
        return tenant_id
    tenant_id = request.headers.get("x-tenant-id")
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header required")
    try:
        tenant_id_int = int(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-Tenant-ID header")
    set_tenant_id(db, tenant_id_int)
    return tenant_id_int


def _rule_to_schema(rule) -> schemas.RecurringRule:
    return schemas.RecurringRule(
        id=rule.id,
        tenant_id=rule.tenant_id,
        account_id=rule.account_id,
        description=rule.description,
        amount=float(rule.amount),
        frequency=schemas.RecurrenceFrequency(rule.frequency),
        start_date=rule.start_date,
        end_date=rule.end_date,
        count=rule.count,
        splits=rule.splits,
        is_active=rule.is_active,
        created_at=datetime.now(timezone.utc),
        last_generated_at=None,
    )


@router.get("/", response_model=list[schemas.RecurringRule])
def list_recurring(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List recurring transaction rules for the current tenant."""
    tenant_id = _wrap_tenant(request, db, current_user)
    rules = list_rules(db, tenant_id=tenant_id, user_id=current_user.id)
    return [_rule_to_schema(r) for r in rules]


@router.post("/", response_model=schemas.RecurringRule, status_code=201)
def create_recurring(
    request: Request,
    payload: schemas.RecurringRuleCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Create a recurring transaction rule."""
    tenant_id = _wrap_tenant(request, db, current_user)
    rule = create_rule(
        db=db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        account_id=payload.account_id,
        description=payload.description,
        amount=Decimal(str(payload.amount)),
        frequency=payload.frequency.value,
        start_date=payload.start_date,
        end_date=payload.end_date,
        count=payload.count,
        splits=[s.model_dump() for s in payload.splits] if payload.splits else None,
    )
    record(
        db,
        current_user,
        AuditAction.CREATE,
        AuditResource.RECURRING_RULE,
        rule.id,
        {"account_id": rule.account_id, "description": rule.description},
    )
    return _rule_to_schema(rule)


@router.put("/{rule_id}", response_model=schemas.RecurringRule)
def update_recurring(
    request: Request,
    rule_id: int,
    payload: schemas.RecurringRuleUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Update a recurring transaction rule."""
    tenant_id = _wrap_tenant(request, db, current_user)
    data = payload.model_dump(exclude_unset=True)
    if "frequency" in data and data["frequency"] is not None:
        data["frequency"] = data["frequency"].value
    if "splits" in data and data["splits"] is not None:
        data["splits"] = [s.model_dump() for s in data["splits"]]
    if "amount" in data and data["amount"] is not None:
        data["amount"] = Decimal(str(data["amount"]))

    rule = update_rule(
        db=db,
        rule_id=rule_id,
        tenant_id=tenant_id,
        user_id=current_user.id,
        **data,
    )
    record(
        db,
        current_user,
        AuditAction.UPDATE,
        AuditResource.RECURRING_RULE,
        rule.id,
        {"updates": list(data.keys())},
    )
    return _rule_to_schema(rule)


@router.delete("/{rule_id}")
def delete_recurring(
    request: Request,
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Delete a recurring rule."""
    tenant_id = _wrap_tenant(request, db, current_user)
    delete_rule(db, rule_id=rule_id, tenant_id=tenant_id, user_id=current_user.id)
    record(
        db,
        current_user,
        AuditAction.DELETE,
        AuditResource.RECURRING_RULE,
        rule_id,
        {},
    )
    return {"ok": True}


@router.post("/{rule_id}/materialize")
def materialize_recurring(
    request: Request,
    rule_id: int,
    as_of: date | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Materialize real transaction(s) from a recurring rule up to ``as_of``."""
    tenant_id = _wrap_tenant(request, db, current_user)
    rule = get_rule(db, rule_id=rule_id, tenant_id=tenant_id, user_id=current_user.id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Recurring rule not found")
    created = materialize_rule(db, rule_id=rule_id, as_of_date=as_of, current_user=current_user)
    record(
        db,
        current_user,
        AuditAction.CREATE,
        AuditResource.TRANSACTION,
        None,
        {"rule_id": rule_id, "materialized": len(created)},
    )
    return {"materialized": len(created), "transactions": created}
