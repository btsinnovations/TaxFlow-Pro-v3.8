from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from .. import models, schemas
from ..rls import is_postgres, set_tenant_id, clear_tenant_id
from .auth import get_current_user

router = APIRouter(prefix="/clients", tags=["clients"])

def _wrap_tenant(request: Request, db: Session):
    if is_postgres() and request.headers.get("x-tenant-id"):
        try:
            set_tenant_id(db, int(request.headers.get("x-tenant-id")))
        except ValueError:
            pass

@router.get("/", response_model=List[schemas.Client])
def list_clients(request: Request, skip: int = 0, limit: int = 100,
                 db: Session = Depends(get_db),
                 current_user: models.User = Depends(get_current_user)):
    _wrap_tenant(request, db)
    return db.query(models.Client).filter(models.Client.user_id == current_user.id).offset(skip).limit(limit).all()

@router.post("/", response_model=schemas.Client)
def create_client(request: Request, client: schemas.ClientCreate,
                  db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    _wrap_tenant(request, db)
    db_client = models.Client(**client.model_dump(), user_id=current_user.id)
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

@router.get("/{client_id}", response_model=schemas.Client)
def get_client(request: Request, client_id: int,
               db: Session = Depends(get_db),
               current_user: models.User = Depends(get_current_user)):
    _wrap_tenant(request, db)
    client = db.query(models.Client).filter(
        models.Client.id == client_id,
        models.Client.user_id == current_user.id
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

@router.patch("/{client_id}", response_model=schemas.Client)
def update_client(request: Request, client_id: int,
                  client_update: schemas.ClientUpdate,
                  db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    _wrap_tenant(request, db)
    client = db.query(models.Client).filter(
        models.Client.id == client_id,
        models.Client.user_id == current_user.id
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    for key, value in client_update.model_dump(exclude_unset=True).items():
        setattr(client, key, value)
    db.commit()
    db.refresh(client)
    return client

@router.delete("/{client_id}")
def delete_client(request: Request, client_id: int,
                  db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    _wrap_tenant(request, db)
    client = db.query(models.Client).filter(
        models.Client.id == client_id,
        models.Client.user_id == current_user.id
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    db.delete(client)
    db.commit()
    return {"ok": True}
