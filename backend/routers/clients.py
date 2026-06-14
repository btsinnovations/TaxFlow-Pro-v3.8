from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from .. import models, schemas
from .auth import get_current_user

router = APIRouter(prefix="/clients", tags=["clients"])

@router.get("/", response_model=List[schemas.Client])
def list_clients(skip: int = 0, limit: int = 100,
                 db: Session = Depends(get_db),
                 current_user: models.User = Depends(get_current_user)):
    return db.query(models.Client).filter(models.Client.user_id == current_user.id).offset(skip).limit(limit).all()

@router.post("/", response_model=schemas.Client)
def create_client(client: schemas.ClientCreate,
                  db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    db_client = models.Client(**client.model_dump(), user_id=current_user.id)
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

@router.get("/{client_id}", response_model=schemas.Client)
def get_client(client_id: int,
               db: Session = Depends(get_db),
               current_user: models.User = Depends(get_current_user)):
    client = db.query(models.Client).filter(
        models.Client.id == client_id,
        models.Client.user_id == current_user.id
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

@router.delete("/{client_id}")
def delete_client(client_id: int,
                  db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    client = db.query(models.Client).filter(
        models.Client.id == client_id,
        models.Client.user_id == current_user.id
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    db.delete(client)
    db.commit()
    return {"ok": True}
