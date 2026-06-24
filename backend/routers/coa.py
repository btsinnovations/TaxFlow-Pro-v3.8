"""Chart of Accounts API endpoints for TaxFlow Pro v3.10."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.routers.auth import get_current_user
from backend.database import get_db
from backend.schemas import COAAccountCreate, COAAccountUpdate, COAAccountTree

router = APIRouter(prefix="/api/coa", tags=["coa"])


@router.get("/", response_model=list[COAAccountTree])
def list_coa(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Return the chart of accounts as a tree."""
    raise NotImplementedError("TASK-3.10.01")


@router.post("/", response_model=COAAccountTree)
def create_account(payload: COAAccountCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Create a new COA account."""
    raise NotImplementedError("TASK-3.10.01")


@router.put("/{account_id}", response_model=COAAccountTree)
def update_account(account_id: int, payload: COAAccountUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Update an existing COA account."""
    raise NotImplementedError("TASK-3.10.01")


@router.delete("/{account_id}")
def delete_account(account_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Soft-delete an inactive COA account."""
    raise NotImplementedError("TASK-3.10.01")
