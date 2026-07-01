from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from .. import models, schemas
from ..rls import is_postgres, resolve_user_tenant_id, set_tenant_id
from ..local import settings as local_settings
from ..audit import record, AuditAction, AuditResource
from ..local.column_encryption import encrypt_for_user, decrypt_for_user
from .auth import get_current_user

router = APIRouter(prefix="/accounts", tags=["accounts"])

def _wrap_tenant(request: Request, db: Session, current_user: models.User):
    if not is_postgres():
        return
    if local_settings.is_single_user():
        set_tenant_id(db, resolve_user_tenant_id(current_user))
        return
    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id is None:
        tenant_id = request.headers.get("x-tenant-id")
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header required")
    set_tenant_id(db, int(tenant_id))

def _decrypt_account(account: models.Account, user: models.User) -> dict:
    return {
        "id": account.id,
        "name": account.name,
        "institution": account.institution,
        "account_number_masked": decrypt_for_user(account.account_number_masked, user),
        "type": account.type,
        "user_id": account.user_id,
        "client_id": account.client_id,
        "tenant_id": account.tenant_id,
        "created_at": account.created_at,
    }


def _decrypt_statement(statement: models.Statement, user: models.User) -> dict:
    return {
        "id": statement.id,
        "account_id": statement.account_id,
        "tenant_id": statement.tenant_id,
        "user_id": statement.user_id,
        "filename": decrypt_for_user(statement.filename, user),
        "period_start": statement.period_start,
        "period_end": statement.period_end,
        "opening_balance": float(statement.opening_balance) if statement.opening_balance is not None else None,
        "closing_balance": float(statement.closing_balance) if statement.closing_balance is not None else None,
        "variance": float(statement.variance) if statement.variance is not None else None,
        "is_balanced": statement.is_balanced,
        "created_at": statement.created_at,
        "transactions": [],
    }


def _decrypt_account_with_statements(account: models.Account, user: models.User) -> dict:
    data = _decrypt_account(account, user)
    data["statements"] = [_decrypt_statement(s, user) for s in account.statements]
    return data


@router.get("/", response_model=List[schemas.Account])
def list_accounts(request: Request, skip: int = 0, limit: int = 100,
                  client_id: int = None,
                  tenant_id: int = None,
                  db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    _wrap_tenant(request, db, current_user)
    query = db.query(models.Account).filter(models.Account.user_id == current_user.id)
    if client_id is not None:
        query = query.filter(models.Account.client_id == client_id)
    if tenant_id is not None:
        query = query.filter(models.Account.tenant_id == tenant_id)
    accounts = query.offset(skip).limit(limit).all()
    return [_decrypt_account(a, current_user) for a in accounts]

@router.post("/", response_model=schemas.Account)
def create_account(request: Request, account: schemas.AccountCreate,
                   db: Session = Depends(get_db),
                   current_user: models.User = Depends(get_current_user)):
    _wrap_tenant(request, db, current_user)
    tenant_id = account.client_id
    db_account = models.Account(
        name=account.name,
        institution=account.institution,
        account_number_masked=encrypt_for_user(account.account_number_masked, current_user),
        type=account.type,
        client_id=account.client_id,
        user_id=current_user.id,
        tenant_id=tenant_id
    )
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    record(db, current_user, AuditAction.CREATE, AuditResource.ACCOUNT, db_account.id,
           {"name": db_account.name, "institution": db_account.institution})
    return _decrypt_account(db_account, current_user)

@router.patch("/{account_id}", response_model=schemas.Account)
def update_account(request: Request, account_id: int,
                   account_update: schemas.AccountUpdate,
                   db: Session = Depends(get_db),
                   current_user: models.User = Depends(get_current_user)):
    _wrap_tenant(request, db, current_user)
    account = db.query(models.Account).filter(
        models.Account.id == account_id,
        models.Account.user_id == current_user.id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    data = account_update.model_dump(exclude_unset=True)
    if "account_number_masked" in data:
        data["account_number_masked"] = encrypt_for_user(data["account_number_masked"], current_user)
    if "client_id" in data:
        data["tenant_id"] = data["client_id"]
    for key, value in data.items():
        setattr(account, key, value)
    db.commit()
    db.refresh(account)
    record(db, current_user, AuditAction.UPDATE, AuditResource.ACCOUNT, account.id,
           {"updated_fields": list(data.keys())})
    return _decrypt_account(account, current_user)

@router.get("/{account_id}", response_model=schemas.AccountWithStatements)
def get_account(request: Request, account_id: int,
                db: Session = Depends(get_db),
                current_user: models.User = Depends(get_current_user)):
    _wrap_tenant(request, db, current_user)
    account = db.query(models.Account).filter(
        models.Account.id == account_id,
        models.Account.user_id == current_user.id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return _decrypt_account_with_statements(account, current_user)

@router.delete("/{account_id}")
def delete_account(request: Request, account_id: int,
                   db: Session = Depends(get_db),
                   current_user: models.User = Depends(get_current_user)):
    _wrap_tenant(request, db, current_user)
    account = db.query(models.Account).filter(
        models.Account.id == account_id,
        models.Account.user_id == current_user.id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    record(db, current_user, AuditAction.DELETE, AuditResource.ACCOUNT, account.id,
           {"name": account.name})
    db.delete(account)
    db.commit()
    return {"ok": True}
