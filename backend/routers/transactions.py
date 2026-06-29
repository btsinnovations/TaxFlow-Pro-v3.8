"""Transaction router for TaxFlow Pro v3.11.03."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List

from .. import models, schemas
from ..database import get_db
from ..rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from ..local import settings as local_settings
from ..audit import record, AuditAction, AuditResource
from ..local.column_encryption import decrypt_for_user, encrypt_for_user
from ..accounting import register as register_logic
from ..accounting.gl_bridge import GLBridge
from .auth import get_current_user

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _wrap_tenant(request: Request, db: Session, current_user: models.User):
    if not is_postgres():
        return
    if local_settings.is_single_user():
        set_tenant_id(db, resolve_user_tenant_id(current_user))
        return
    tenant_id = request.headers.get("x-tenant-id")
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header required")
    set_tenant_id(db, int(tenant_id))


def _resolve_tenant_id(request: Request, current_user: models.User) -> int:
    if not is_postgres():
        return resolve_user_tenant_id(current_user)
    if local_settings.is_single_user():
        return resolve_user_tenant_id(current_user)
    tenant_id = request.headers.get("x-tenant-id")
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header required")
    return int(tenant_id)


def _transaction_response(tx: models.Transaction, user: models.User) -> dict:
    return {
        "id": tx.id,
        "date": tx.date.isoformat() if tx.date else None,
        "description": decrypt_for_user(tx.description, user),
        "amount": float(tx.amount) if tx.amount is not None else None,
        "tx_type": tx.tx_type,
        "category": tx.category,
        "running_balance": float(tx.running_balance) if tx.running_balance is not None else None,
        "workpaper_ref": tx.workpaper_ref,
        "statement_id": tx.statement_id,
        "tenant_id": tx.tenant_id,
        "gl_account_id": tx.gl_account_id,
        "created_at": tx.created_at.isoformat() if tx.created_at else None,
    }


@router.get("/", response_model=List[schemas.Transaction])
def list_transactions(
    request: Request,
    account_id: int = None,
    tenant_id: int = None,
    q: str = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    effective_tenant_id = _resolve_tenant_id(request, current_user) if tenant_id is None else tenant_id
    _wrap_tenant(request, db, current_user)
    filters = {
        "tenant_id": effective_tenant_id,
        "user_id": current_user.id,
        "limit": limit,
        "offset": offset,
    }
    if account_id is not None:
        filters["account_id"] = account_id
    if q:
        filters["q"] = q
    transactions = register_logic.list_transactions(db, effective_tenant_id, filters)
    return [_transaction_response(tx, current_user) for tx in transactions]


@router.post("/", response_model=schemas.Transaction, status_code=201)
def create_transaction(
    request: Request,
    data: schemas.TransactionDirectCreate,
    tenant_id: int = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    effective_tenant_id = _resolve_tenant_id(request, current_user) if tenant_id is None else tenant_id
    _wrap_tenant(request, db, current_user)

    account = (
        db.query(models.Account)
        .filter(
            models.Account.id == data.account_id,
            models.Account.user_id == current_user.id,
        )
        .first()
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    synthetic_statement = (
        db.query(models.Statement)
        .filter(
            models.Statement.account_id == account.id,
            models.Statement.filename == "__register__",
        )
        .first()
    )
    if synthetic_statement is None:
        synthetic_statement = models.Statement(
            account_id=account.id,
            tenant_id=effective_tenant_id,
            user_id=current_user.id,
            filename="__register__",
        )
        db.add(synthetic_statement)
        db.commit()
        db.refresh(synthetic_statement)

    description = data.description
    if data.payee:
        description = f"{data.payee} — {description}"

    tx = models.Transaction(
        statement_id=synthetic_statement.id,
        tenant_id=effective_tenant_id,
        user_id=current_user.id,
        date=data.date,
        description=encrypt_for_user(description, current_user),
        amount=data.amount,
        tx_type=data.tx_type,
        category=data.category,
        gl_account_id=data.gl_account_id,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    record(db, current_user, AuditAction.CREATE, AuditResource.TRANSACTION, tx.id,
           {"amount": str(tx.amount), "category": tx.category, "gl_account_id": tx.gl_account_id})
    return _transaction_response(tx, current_user)


@router.patch("/{transaction_id}", response_model=schemas.Transaction)
def update_transaction(
    request: Request,
    transaction_id: int,
    update: schemas.TransactionDirectUpdate,
    tenant_id: int = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    effective_tenant_id = _resolve_tenant_id(request, current_user) if tenant_id is None else tenant_id
    _wrap_tenant(request, db, current_user)
    data = update.model_dump(exclude_unset=True)
    if "description" in data and data["description"]:
        data["description"] = encrypt_for_user(data["description"], current_user)
    try:
        tx = register_logic.update_transaction(
            db,
            transaction_id,
            tenant_id=effective_tenant_id,
            user_id=current_user.id,
            description=data.get("description"),
            amount=data.get("amount"),
            date_value=data.get("date"),
            category=data.get("category"),
            gl_account_id=data.get("gl_account_id"),
        )
    except register_logic.RegisterError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    record(db, current_user, AuditAction.UPDATE, AuditResource.TRANSACTION, tx.id,
           {"updated_fields": list(data.keys())})
    return _transaction_response(tx, current_user)


@router.delete("/{transaction_id}")
def delete_transaction(
    request: Request,
    transaction_id: int,
    tenant_id: int = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    effective_tenant_id = _resolve_tenant_id(request, current_user) if tenant_id is None else tenant_id
    _wrap_tenant(request, db, current_user)
    try:
        register_logic.delete_transaction(
            db,
            transaction_id,
            tenant_id=effective_tenant_id,
            user_id=current_user.id,
        )
    except register_logic.RegisterError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    record(db, current_user, AuditAction.DELETE, AuditResource.TRANSACTION, transaction_id,
           {})
    return {"ok": True}


@router.get("/{transaction_id}/running-balance")
def get_running_balance(
    request: Request,
    transaction_id: int,
    tenant_id: int = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    effective_tenant_id = _resolve_tenant_id(request, current_user) if tenant_id is None else tenant_id
    _wrap_tenant(request, db, current_user)
    tx = (
        db.query(models.Transaction)
        .filter(
            models.Transaction.id == transaction_id,
            models.Transaction.tenant_id == effective_tenant_id,
            models.Transaction.user_id == current_user.id,
        )
        .first()
    )
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    statement = db.query(models.Statement).filter(models.Statement.id == tx.statement_id).first()
    if statement is None:
        raise HTTPException(status_code=404, detail="Statement not found")
    try:
        rows = register_logic.compute_running_balance(db, statement.account_id)
    except register_logic.RegisterError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"account_id": statement.account_id, "rows": rows}


@router.put("/{transaction_id}/workpaper-ref", response_model=schemas.Transaction)
def update_workpaper_ref(
    request: Request,
    transaction_id: int,
    tenant_id: int,
    update: schemas.WorkpaperRefUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _wrap_tenant(request, db, current_user)
    tx = db.query(models.Transaction).filter(
        models.Transaction.id == transaction_id,
        models.Transaction.tenant_id == tenant_id,
        models.Transaction.user_id == current_user.id,
    ).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    tx.workpaper_ref = update.workpaper_ref
    db.commit()
    db.refresh(tx)
    record(db, current_user, AuditAction.UPDATE, AuditResource.TRANSACTION, tx.id,
           {"workpaper_ref": tx.workpaper_ref})
    return _transaction_response(tx, current_user)
