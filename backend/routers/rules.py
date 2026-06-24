"""Categorization rules router for TaxFlow Pro v3.9."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from ..local import settings as local_settings
from ..audit import record, AuditAction, AuditResource
from .auth import get_current_user

router = APIRouter(prefix="/rules", tags=["rules"])


def _resolve_tenant_id(request: Request, current_user: models.User) -> int:
    if local_settings.is_single_user():
        return resolve_user_tenant_id(current_user)
    tenant_id = request.headers.get("x-tenant-id")
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header required")
    return int(tenant_id)


def _wrap_tenant(request: Request, db: Session, current_user: models.User):
    if not is_postgres():
        return
    set_tenant_id(db, _resolve_tenant_id(request, current_user))


@router.get("/", response_model=List[schemas.CategorizationRuleOut])
def list_rules(
    request: Request,
    tenant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    effective_tenant_id = _resolve_tenant_id(request, current_user) if tenant_id is None else tenant_id
    _wrap_tenant(request, db, current_user)
    return db.query(models.CategorizationRule).filter(
        models.CategorizationRule.tenant_id == effective_tenant_id,
        models.CategorizationRule.user_id == current_user.id,
    ).order_by(models.CategorizationRule.priority.desc()).all()


@router.post("/", response_model=schemas.CategorizationRuleOut)
def create_rule(
    request: Request,
    rule: schemas.CategorizationRuleCreate,
    tenant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    effective_tenant_id = _resolve_tenant_id(request, current_user) if tenant_id is None else tenant_id
    _wrap_tenant(request, db, current_user)
    account = db.query(models.GLAccount).filter(
        models.GLAccount.id == rule.gl_account_id,
        models.GLAccount.tenant_id == effective_tenant_id,
        models.GLAccount.user_id == current_user.id,
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="GL account not found")

    db_rule = models.CategorizationRule(
        tenant_id=effective_tenant_id,
        user_id=current_user.id,
        name=rule.name,
        pattern=rule.pattern,
        gl_account_id=rule.gl_account_id,
        priority=rule.priority,
        enabled=rule.enabled,
    )
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    record(db, current_user, AuditAction.CREATE, AuditResource.CATEGORIZATION_RULE, db_rule.id,
           {"name": db_rule.name, "pattern": db_rule.pattern, "gl_account_id": db_rule.gl_account_id})
    return db_rule


@router.get("/{rule_id}", response_model=schemas.CategorizationRuleOut)
def get_rule(
    request: Request,
    rule_id: int,
    tenant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    effective_tenant_id = _resolve_tenant_id(request, current_user) if tenant_id is None else tenant_id
    _wrap_tenant(request, db, current_user)
    rule = db.query(models.CategorizationRule).filter(
        models.CategorizationRule.id == rule_id,
        models.CategorizationRule.tenant_id == effective_tenant_id,
        models.CategorizationRule.user_id == current_user.id,
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.put("/{rule_id}", response_model=schemas.CategorizationRuleOut)
def update_rule(
    request: Request,
    rule_id: int,
    update: schemas.CategorizationRuleUpdate,
    tenant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    effective_tenant_id = _resolve_tenant_id(request, current_user) if tenant_id is None else tenant_id
    _wrap_tenant(request, db, current_user)
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
    record(db, current_user, AuditAction.UPDATE, AuditResource.CATEGORIZATION_RULE, rule.id,
           {"updated_fields": list(data.keys())})
    return rule


@router.delete("/{rule_id}")
def delete_rule(
    request: Request,
    rule_id: int,
    tenant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    effective_tenant_id = _resolve_tenant_id(request, current_user) if tenant_id is None else tenant_id
    _wrap_tenant(request, db, current_user)
    rule = db.query(models.CategorizationRule).filter(
        models.CategorizationRule.id == rule_id,
        models.CategorizationRule.tenant_id == effective_tenant_id,
        models.CategorizationRule.user_id == current_user.id,
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    record(db, current_user, AuditAction.DELETE, AuditResource.CATEGORIZATION_RULE, rule.id,
           {"name": rule.name})
    db.delete(rule)
    db.commit()
    return {"ok": True}
