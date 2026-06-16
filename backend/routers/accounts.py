<<<<<<< HEAD
from fastapi import APIRouter, Depends, HTTPException
=======
from fastapi import APIRouter, Depends, HTTPException, Request
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from .. import models, schemas
<<<<<<< HEAD
=======
from ..rls import is_postgres, set_tenant_id
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
from .auth import get_current_user

router = APIRouter(prefix="/accounts", tags=["accounts"])

<<<<<<< HEAD
@router.get("/", response_model=List[schemas.Account])
def list_accounts(skip: int = 0, limit: int = 100,
                  db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    return db.query(models.Account).filter(models.Account.user_id == current_user.id).offset(skip).limit(limit).all()

@router.post("/", response_model=schemas.Account)
def create_account(account: schemas.AccountCreate,
                   db: Session = Depends(get_db),
                   current_user: models.User = Depends(get_current_user)):
    db_account = models.Account(**account.model_dump(), user_id=current_user.id)
=======
def _wrap_tenant(request: Request, db: Session):
    if is_postgres() and request.headers.get("x-tenant-id"):
        try:
            set_tenant_id(db, int(request.headers.get("x-tenant-id")))
        except ValueError:
            pass

@router.get("/", response_model=List[schemas.Account])
def list_accounts(request: Request, skip: int = 0, limit: int = 100,
                  client_id: int = None,
                  tenant_id: int = None,
                  db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    _wrap_tenant(request, db)
    query = db.query(models.Account).filter(models.Account.user_id == current_user.id)
    if client_id is not None:
        query = query.filter(models.Account.client_id == client_id)
    if tenant_id is not None:
        query = query.filter(models.Account.tenant_id == tenant_id)
    return query.offset(skip).limit(limit).all()

@router.post("/", response_model=schemas.Account)
def create_account(request: Request, account: schemas.AccountCreate,
                   db: Session = Depends(get_db),
                   current_user: models.User = Depends(get_current_user)):
    _wrap_tenant(request, db)
    tenant_id = account.client_id
    db_account = models.Account(
        **account.model_dump(),
        user_id=current_user.id,
        tenant_id=tenant_id
    )
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    return db_account

<<<<<<< HEAD
@router.get("/{account_id}", response_model=schemas.AccountWithStatements)
def get_account(account_id: int,
                db: Session = Depends(get_db),
                current_user: models.User = Depends(get_current_user)):
=======
@router.patch("/{account_id}", response_model=schemas.Account)
def update_account(request: Request, account_id: int,
                   account_update: schemas.AccountUpdate,
                   db: Session = Depends(get_db),
                   current_user: models.User = Depends(get_current_user)):
    _wrap_tenant(request, db)
    account = db.query(models.Account).filter(
        models.Account.id == account_id,
        models.Account.user_id == current_user.id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    data = account_update.model_dump(exclude_unset=True)
    if "client_id" in data:
        data["tenant_id"] = data["client_id"]
    for key, value in data.items():
        setattr(account, key, value)
    db.commit()
    db.refresh(account)
    return account

@router.get("/{account_id}", response_model=schemas.AccountWithStatements)
def get_account(request: Request, account_id: int,
                db: Session = Depends(get_db),
                current_user: models.User = Depends(get_current_user)):
    _wrap_tenant(request, db)
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
    account = db.query(models.Account).filter(
        models.Account.id == account_id,
        models.Account.user_id == current_user.id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account

@router.delete("/{account_id}")
<<<<<<< HEAD
def delete_account(account_id: int,
                   db: Session = Depends(get_db),
                   current_user: models.User = Depends(get_current_user)):
=======
def delete_account(request: Request, account_id: int,
                   db: Session = Depends(get_db),
                   current_user: models.User = Depends(get_current_user)):
    _wrap_tenant(request, db)
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
    account = db.query(models.Account).filter(
        models.Account.id == account_id,
        models.Account.user_id == current_user.id
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(account)
    db.commit()
    return {"ok": True}
