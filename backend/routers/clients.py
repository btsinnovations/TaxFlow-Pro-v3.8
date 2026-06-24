from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from .. import models, schemas
from ..rls import is_postgres, resolve_user_tenant_id, set_tenant_id, clear_tenant_id
from ..local import settings as local_settings
from ..audit import record, AuditAction, AuditResource
from ..local.column_encryption import encrypt_for_user, decrypt_for_user
from .auth import get_current_user

router = APIRouter(prefix="/clients", tags=["clients"])

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

def _decrypt_client(client: models.Client, user: models.User) -> dict:
    data = {
        "id": client.id,
        "name": client.name,
        "email": client.email,
        "tax_id": decrypt_for_user(client.tax_id, user),
        "user_id": client.user_id,
        "created_at": client.created_at,
    }
    return data

@router.get("/", response_model=List[schemas.Client])
def list_clients(request: Request, skip: int = 0, limit: int = 100,
                 db: Session = Depends(get_db),
                 current_user: models.User = Depends(get_current_user)):
    _wrap_tenant(request, db, current_user)
    clients = db.query(models.Client).filter(models.Client.user_id == current_user.id).offset(skip).limit(limit).all()
    return [_decrypt_client(c, current_user) for c in clients]

@router.post("/", response_model=schemas.Client)
def create_client(request: Request, client: schemas.ClientCreate,
                  db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    _wrap_tenant(request, db, current_user)
    db_client = models.Client(
        name=client.name,
        email=client.email,
        tax_id=encrypt_for_user(client.tax_id, current_user),
        user_id=current_user.id,
    )
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    record(db, current_user, AuditAction.CREATE, AuditResource.CLIENT, db_client.id,
           {"name": db_client.name})
    return _decrypt_client(db_client, current_user)

@router.get("/{client_id}", response_model=schemas.Client)
def get_client(request: Request, client_id: int,
               db: Session = Depends(get_db),
               current_user: models.User = Depends(get_current_user)):
    _wrap_tenant(request, db, current_user)
    client = db.query(models.Client).filter(
        models.Client.id == client_id,
        models.Client.user_id == current_user.id
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return _decrypt_client(client, current_user)

@router.patch("/{client_id}", response_model=schemas.Client)
def update_client(request: Request, client_id: int,
                  client_update: schemas.ClientUpdate,
                  db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    _wrap_tenant(request, db, current_user)
    client = db.query(models.Client).filter(
        models.Client.id == client_id,
        models.Client.user_id == current_user.id
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    data = client_update.model_dump(exclude_unset=True)
    if "tax_id" in data:
        data["tax_id"] = encrypt_for_user(data["tax_id"], current_user)
    for key, value in data.items():
        setattr(client, key, value)
    db.commit()
    db.refresh(client)
    record(db, current_user, AuditAction.UPDATE, AuditResource.CLIENT, client.id,
           {"updated_fields": list(client_update.model_dump(exclude_unset=True).keys())})
    return _decrypt_client(client, current_user)

@router.delete("/{client_id}")
def delete_client(request: Request, client_id: int,
                  db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    _wrap_tenant(request, db, current_user)
    client = db.query(models.Client).filter(
        models.Client.id == client_id,
        models.Client.user_id == current_user.id
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    record(db, current_user, AuditAction.DELETE, AuditResource.CLIENT, client.id,
           {"name": client.name})
    db.delete(client)
    db.commit()
    return {"ok": True}
